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
            "realtimeEligible": bool(previous.get("realtimeEligible", False)),
            "tradeEligible": False,
        }
    registry["updatedAt"] = _now()
    _write(registry, path)
    return registry


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

    if review.get("research_complete") is not True:
        raise ScoutRegistryError("Research must be complete")
    if review.get("assistant_research_complete") is not True:
        raise ScoutRegistryError("Assistant research must be complete")
    if review.get("user_confirmed") is not True:
        raise ScoutRegistryError("Explicit user confirmation is required")

    decision = str(review.get("final_decision") or "").upper()
    if decision not in {"PASS", "WATCH", "APPROVED"}:
        raise ScoutRegistryError("Final decision must be PASS, WATCH, or APPROVED")

    thesis = str(review.get("thesis") or "").strip()
    bear_case = str(review.get("bear_case") or "").strip()
    invalidation = str(review.get("invalidation") or "").strip()
    risks = [str(x).strip() for x in (review.get("key_risks") or []) if str(x).strip()]
    if not thesis or not bear_case or not invalidation or not risks:
        raise ScoutRegistryError("Thesis, bear case, key risks, and invalidation are required")

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
        "thesis": thesis,
        "bearCase": bear_case,
        "keyRisks": risks,
        "invalidation": invalidation,
        "assistantResearchComplete": True,
        "userConfirmed": True,
        "finalDecision": decision,
    }
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
