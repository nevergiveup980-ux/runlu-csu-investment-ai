"""Private local registry for RUNLU Scout V1 research candidates.

Scout discovery never grants trading authority. A candidate can move beyond
RESEARCH_REQUIRED only after assistant research is complete and the user
explicitly confirms a final PASS/WATCH/APPROVED decision.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from scout_recheck import build_recheck_packet, evaluate_recheck
from scout_research_writeback import (
    DEFAULT_ARCHIVE,
    ResearchWritebackError,
    archive_research_result,
    validate_research_result,
)

DEFAULT_REGISTRY = Path(".csu-private") / "scout-registry.json"


class ScoutRegistryError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read(path: Path = DEFAULT_REGISTRY) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "candidates": {}}
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoutRegistryError("Scout registry is unavailable or corrupt") from exc
    if not isinstance(value, dict) or not isinstance(value.get("candidates"), dict):
        raise ScoutRegistryError("Scout registry format is invalid")
    return value


def _write(value: Dict[str, Any], path: Path = DEFAULT_REGISTRY) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="scout-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def record_scan(scan_result: Dict[str, Any], path: Path = DEFAULT_REGISTRY) -> Dict[str, Any]:
    if scan_result.get("mode") != "DISCOVERY_RESEARCH_ONLY":
        raise ScoutRegistryError("Only research-only Scout scans may be recorded")
    candidates = scan_result.get("candidates")
    if not isinstance(candidates, list):
        raise ScoutRegistryError("Scout scan candidates are missing")

    registry = _read(path)
    saved = registry["candidates"]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        symbol = str(candidate.get("symbol") or "").upper()
        if not symbol.endswith(":TSX"):
            raise ScoutRegistryError("Scout registry accepts TSX candidates only")
        previous = saved.get(symbol) or {}
        stage = previous.get("stage") or "RESEARCH_REQUIRED"
        previous_score = previous.get("latestScore")
        saved[symbol] = {
            "symbol": symbol,
            "stage": stage,
            "latestScore": int(candidate.get("score") or 0),
            "tier": str(candidate.get("tier") or "PASS_FOR_NOW"),
            "reasons": [str(x) for x in (candidate.get("reasons") or [])][:20],
            "riskFlags": [str(x) for x in (candidate.get("riskFlags") or [])][:20],
            "marketDataAsOf": candidate.get("marketDataAsOf"),
            "lastScannedAt": _now(),
            "research": previous.get("research"),
            "researchDraft": previous.get("researchDraft"),
            "researchStatus": previous.get("researchStatus") or "PENDING",
            "decisionHistory": list(previous.get("decisionHistory") or []),
            "realtimeEligible": bool(previous.get("realtimeEligible", False)),
            "tradeEligible": False,
            "recheck": previous.get("recheck"),
        }

        current_row = saved[symbol]
        evaluation = evaluate_recheck(current_row, previous_score=previous_score)
        if evaluation["recheckRequired"]:
            packet = build_recheck_packet(current_row, evaluation)
            current_row["recheck"] = packet
            current_row["previousStageBeforeRecheck"] = stage
            current_row["stage"] = "RECHECK_REQUIRED"
            current_row["researchStatus"] = "RECHECK_REQUIRED"
            current_row["realtimeEligible"] = False
            current_row["tradeEligible"] = False
    registry["updatedAt"] = _now()
    _write(registry, path)
    return registry


def flag_material_recheck(
    symbol: str,
    *,
    events=(),
    previous_price: float | None = None,
    current_price: float | None = None,
    path: Path = DEFAULT_REGISTRY,
) -> Dict[str, Any]:
    registry = _read(path)
    key = str(symbol or "").upper()
    candidate = registry["candidates"].get(key)
    if not candidate:
        raise ScoutRegistryError("Unknown Scout candidate")

    evaluation = evaluate_recheck(
        candidate,
        previous_score=candidate.get("latestScore"),
        previous_price=previous_price,
        current_price=current_price,
        events=events,
    )
    if not evaluation["recheckRequired"]:
        return candidate

    previous_stage = candidate.get("stage")
    candidate["recheck"] = build_recheck_packet(candidate, evaluation)
    candidate["previousStageBeforeRecheck"] = previous_stage
    candidate["stage"] = "RECHECK_REQUIRED"
    candidate["researchStatus"] = "RECHECK_REQUIRED"
    candidate["realtimeEligible"] = False
    candidate["tradeEligible"] = False
    registry["updatedAt"] = _now()
    _write(registry, path)
    return candidate


def record_assistant_research(
    symbol: str,
    packet: Dict[str, Any],
    path: Path = DEFAULT_REGISTRY,
    archive_path: Path = DEFAULT_ARCHIVE,
) -> Dict[str, Any]:
    registry = _read(path)
    key = str(symbol or "").upper()
    candidate = registry["candidates"].get(key)
    if not candidate:
        raise ScoutRegistryError("Unknown Scout candidate")
    if candidate.get("stage") == "PASS":
        raise ScoutRegistryError("PASS candidate cannot receive new assistant research without re-opening")
    is_recheck = candidate.get("stage") == "RECHECK_REQUIRED"

    try:
        validated = validate_research_result(packet, candidate)
        archived = archive_research_result(validated, archive_path)
    except ResearchWritebackError as exc:
        raise ScoutRegistryError(str(exc)) from exc

    candidate["researchDraft"] = {
        "archiveVersion": archived["version"],
        "digest": archived["digest"],
        "completedAt": archived["completedAt"],
        "research": archived["research"],
        "evidence": archived["evidence"],
        "assistantResearchComplete": True,
        "userConfirmed": False,
        "finalDecision": None,
    }
    candidate["researchStatus"] = "ASSISTANT_COMPLETE_AWAITING_USER"
    candidate["stage"] = "RESEARCH_REQUIRED"
    if is_recheck:
        candidate["researchDraft"]["recheckOfDigest"] = (
            (candidate.get("recheck") or {}).get("previousResearchDigest")
        )
    candidate["realtimeEligible"] = False
    candidate["tradeEligible"] = False
    registry["updatedAt"] = _now()
    _write(registry, path)
    return candidate


def apply_joint_review(
    symbol: str,
    review: Dict[str, Any],
    path: Path = DEFAULT_REGISTRY,
) -> Dict[str, Any]:
    registry = _read(path)
    key = str(symbol or "").upper()
    candidate = registry["candidates"].get(key)
    if not candidate:
        raise ScoutRegistryError("Unknown Scout candidate")

    draft = candidate.get("researchDraft")
    if not isinstance(draft, dict) or draft.get("assistantResearchComplete") is not True:
        raise ScoutRegistryError("Completed assistant research must be written back before joint review")
    if candidate.get("researchStatus") != "ASSISTANT_COMPLETE_AWAITING_USER":
        raise ScoutRegistryError("Candidate is not awaiting user confirmation")
    if review.get("user_confirmed") is not True:
        raise ScoutRegistryError("Explicit user confirmation is required")

    expected_digest = str(draft.get("digest") or "")
    supplied_digest = str(review.get("research_digest") or "")
    if not supplied_digest:
        raise ScoutRegistryError("Joint review must include the archived research digest")
    if supplied_digest != expected_digest:
        raise ScoutRegistryError("Joint review research digest does not match archived research")

    decision = str(review.get("final_decision") or "").upper()
    if decision not in {"PASS", "WATCH", "APPROVED"}:
        raise ScoutRegistryError("Final decision must be PASS, WATCH, or APPROVED")

    research = draft.get("research") or {}
    thesis = str(research.get("bull_case") or "").strip()
    bear_case = str(research.get("bear_case") or "").strip()
    invalidation = str(research.get("invalidation_condition") or "").strip()
    risks = [str(x).strip() for x in (research.get("key_risks") or []) if str(x).strip()]
    if not thesis or not bear_case or not invalidation or not risks:
        raise ScoutRegistryError("Archived research is missing thesis, bear case, risks, or invalidation")

    stage = {
        "PASS": "PASS",
        "WATCH": "WATCH",
        "APPROVED": "APPROVED_UNIVERSE",
    }[decision]
    candidate["stage"] = stage
    candidate["realtimeEligible"] = stage in {"WATCH", "APPROVED_UNIVERSE"}
    candidate["tradeEligible"] = False
    candidate["research"] = {
        "completedAt": _now(),
        "researchDigest": expected_digest,
        "archiveVersion": draft.get("archiveVersion"),
        "thesis": thesis,
        "bearCase": bear_case,
        "keyRisks": risks,
        "invalidation": invalidation,
        "evidence": draft.get("evidence") or {},
        "assistantResearchComplete": True,
        "userConfirmed": True,
        "finalDecision": decision,
    }
    candidate["researchStatus"] = "FINALIZED"
    history = candidate.setdefault("decisionHistory", [])
    history.append({
        "decidedAt": _now(),
        "finalDecision": decision,
        "stage": stage,
        "researchDigest": expected_digest,
        "archiveVersion": draft.get("archiveVersion"),
        "userConfirmed": True,
        "tradeEligible": False,
    })
    candidate["decisionHistory"] = history[-20:]
    registry["updatedAt"] = _now()
    _write(registry, path)
    return candidate


def ranked_candidates(path: Path = DEFAULT_REGISTRY) -> List[Dict[str, Any]]:
    registry = _read(path)
    values = list(registry["candidates"].values())
    return sorted(values, key=lambda x: int(x.get("latestScore") or 0), reverse=True)


def execution_eligible_symbols(path: Path = DEFAULT_REGISTRY) -> List[str]:
    # Scout V1 intentionally grants no execution authority.
    return []
