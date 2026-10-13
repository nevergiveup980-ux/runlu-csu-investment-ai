"""RUNLU Scout research writeback and immutable local archive.

Assistant research may be written back only as a completed, evidenced dossier.
It moves a candidate to AWAITING_USER_CONFIRMATION but never grants realtime or
trading authority. Final PASS/WATCH/APPROVED remains a separate user-confirmed
registry action.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from scout_research_card import build_research_card, card_completion

DEFAULT_ARCHIVE = Path(".csu-private") / "scout-research-archive.json"


class ResearchWritebackError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def research_digest(research: Dict[str, Any]) -> str:
    canonical = json.dumps(
        research,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_result_template(candidate: Dict[str, Any]) -> Dict[str, Any]:
    card = build_research_card(candidate)
    return {
        "kind": "RUNLU_SCOUT_RESEARCH_RESULT",
        "version": 1,
        "symbol": card["symbol"],
        "research": card["research"],
        "assistantResearchComplete": False,
        "userConfirmed": False,
        "finalDecision": None,
        "authority": {
            "researchOnly": True,
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        },
    }


def validate_research_result(packet: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(packet, dict):
        raise ResearchWritebackError("Research result must be an object")
    if packet.get("kind") != "RUNLU_SCOUT_RESEARCH_RESULT" or packet.get("version") != 1:
        raise ResearchWritebackError("Unsupported research result packet")

    expected_symbol = str(candidate.get("symbol") or "").upper()
    symbol = str(packet.get("symbol") or "").upper()
    if symbol != expected_symbol or not symbol.endswith(":TSX"):
        raise ResearchWritebackError("Research result symbol does not match candidate")

    if packet.get("assistantResearchComplete") is not True:
        raise ResearchWritebackError("Assistant research must be explicitly complete")
    if packet.get("userConfirmed") not in (False, None):
        raise ResearchWritebackError("Assistant writeback cannot contain user confirmation")
    if packet.get("finalDecision") not in (None, ""):
        raise ResearchWritebackError("Assistant writeback cannot contain a final investment decision")

    research = packet.get("research")
    if not isinstance(research, dict):
        raise ResearchWritebackError("Research result is missing structured research")

    card = build_research_card(candidate)
    card["research"] = research
    completion = card_completion(card)
    if not completion["complete"]:
        raise ResearchWritebackError(
            "Research result is incomplete: " + ", ".join(completion["missing"])
        )

    sanitized = {
        "business_model": str(research.get("business_model") or "").strip(),
        "financial_quality": str(research.get("financial_quality") or "").strip(),
        "valuation": str(research.get("valuation") or "").strip(),
        "industry_and_competition": str(research.get("industry_and_competition") or "").strip(),
        "management_and_governance": str(research.get("management_and_governance") or "").strip(),
        "recent_news_and_catalysts": str(research.get("recent_news_and_catalysts") or "").strip(),
        "bull_case": str(research.get("bull_case") or "").strip(),
        "bear_case": str(research.get("bear_case") or "").strip(),
        "key_risks": [str(x).strip() for x in research.get("key_risks", []) if str(x).strip()],
        "what_could_make_us_wrong": str(research.get("what_could_make_us_wrong") or "").strip(),
        "invalidation_condition": str(research.get("invalidation_condition") or "").strip(),
        "sources": completion["evidence"]["acceptedSources"],
    }

    return {
        "symbol": symbol,
        "research": sanitized,
        "digest": research_digest(sanitized),
        "evidence": {
            "sourceCount": completion["evidence"]["sourceCount"],
            "primarySourceCount": completion["evidence"]["primarySourceCount"],
            "independentSourceCount": completion["evidence"]["independentSourceCount"],
            "recentNewsCount": completion["evidence"]["recentNewsCount"],
        },
        "completedAt": _now(),
        "assistantResearchComplete": True,
        "userConfirmed": False,
        "finalDecision": None,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


def _read_archive(path: Path = DEFAULT_ARCHIVE) -> Dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "records": {}}
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchWritebackError("Research archive is unavailable or corrupt") from exc
    if not isinstance(value, dict) or not isinstance(value.get("records"), dict):
        raise ResearchWritebackError("Research archive format is invalid")
    return value


def _write_archive(value: Dict[str, Any], path: Path = DEFAULT_ARCHIVE) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="scout-research-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def archive_research_result(
    validated: Dict[str, Any],
    path: Path = DEFAULT_ARCHIVE,
) -> Dict[str, Any]:
    symbol = validated["symbol"]
    archive = _read_archive(path)
    history = archive["records"].setdefault(symbol, [])

    if any(row.get("digest") == validated["digest"] for row in history):
        raise ResearchWritebackError("Identical research result is already archived")

    version = len(history) + 1
    record = {
        **validated,
        "version": version,
        "archivedAt": _now(),
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }
    history.append(record)
    archive["updatedAt"] = _now()
    _write_archive(archive, path)
    return record
