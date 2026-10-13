"""RUNLU Scout research recheck engine.

Detects material changes after a WATCH / APPROVED_UNIVERSE verdict and reopens
joint due diligence. Rechecks never grant trading authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

RECHECKABLE_STAGES = {"WATCH", "APPROVED_UNIVERSE"}
MATERIAL_SCORE_MOVE = 15
MATERIAL_PRICE_MOVE_PCT = 12.0
MAX_RESEARCH_AGE_DAYS = 120
TRIGGER_TYPES = {
    "EARNINGS",
    "GUIDANCE",
    "M_AND_A",
    "MANAGEMENT_CHANGE",
    "REGULATORY",
    "CAPITAL_RAISE",
    "DIVIDEND_CHANGE",
    "CREDIT_EVENT",
    "LITIGATION",
    "MATERIAL_NEWS",
}


class ScoutRecheckError(RuntimeError):
    pass


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_details(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "").upper()
        if event_type not in TRIGGER_TYPES:
            continue
        event_id = str(event.get("id") or "").strip()
        title = str(event.get("title") or "").strip()[:240]
        key = event_id or f"{event_type}:{title}"
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": event_id or None,
            "type": event_type,
            "title": title or None,
            "datetime": event.get("datetime"),
            "sourceType": str(event.get("sourceType") or "") or None,
        })
        if len(out) >= 10:
            break
    return out


def evaluate_recheck(
    candidate: Dict[str, Any],
    *,
    previous_score: int | None = None,
    previous_price: float | None = None,
    current_price: float | None = None,
    events: Iterable[Dict[str, Any]] = (),
    now: datetime | None = None,
) -> Dict[str, Any]:
    stage = str(candidate.get("stage") or "").upper()
    if stage not in RECHECKABLE_STAGES:
        return {
            "recheckRequired": False,
            "reasons": [],
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        }

    reasons: List[str] = []
    latest_score = int(candidate.get("latestScore") or 0)
    if previous_score is not None and abs(latest_score - int(previous_score)) >= MATERIAL_SCORE_MOVE:
        reasons.append(f"SCOUT_SCORE_MOVE:{int(previous_score)}->{latest_score}")

    if previous_price and current_price and previous_price > 0 and current_price > 0:
        move = ((float(current_price) / float(previous_price)) - 1.0) * 100.0
        if abs(move) >= MATERIAL_PRICE_MOVE_PCT:
            reasons.append(f"PRICE_MOVE_PCT:{move:.2f}")

    event_details = _event_details(events)
    event_types = list(dict.fromkeys(x["type"] for x in event_details))
    reasons.extend(f"EVENT:{x}" for x in event_types)

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    research = candidate.get("research") if isinstance(candidate.get("research"), dict) else {}
    completed = _parse_iso(research.get("completedAt"))
    if completed is not None and (current - completed).days >= MAX_RESEARCH_AGE_DAYS:
        reasons.append(f"RESEARCH_AGE_DAYS:{(current - completed).days}")

    return {
        "recheckRequired": bool(reasons),
        "reasons": reasons,
        "eventTypes": event_types,
        "eventDetails": event_details,
        "previousScore": previous_score,
        "currentScore": latest_score,
        "previousPrice": previous_price,
        "currentPrice": current_price,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }


def build_recheck_packet(candidate: Dict[str, Any], evaluation: Dict[str, Any]) -> Dict[str, Any]:
    if not evaluation.get("recheckRequired"):
        raise ScoutRecheckError("No material change requires a research recheck")
    symbol = str(candidate.get("symbol") or "").upper()
    if not symbol.endswith(":TSX"):
        raise ScoutRecheckError("Research recheck requires a TSX candidate")
    research = candidate.get("research") if isinstance(candidate.get("research"), dict) else {}
    return {
        "kind": "RUNLU_SCOUT_RECHECK",
        "version": 1,
        "symbol": symbol,
        "previousStage": candidate.get("stage"),
        "previousDecision": research.get("finalDecision"),
        "previousResearchDigest": research.get("researchDigest"),
        "reasons": list(evaluation.get("reasons") or []),
        "eventTypes": list(evaluation.get("eventTypes") or []),
        "eventDetails": list(evaluation.get("eventDetails") or []),
        "score": {
            "previous": evaluation.get("previousScore"),
            "current": evaluation.get("currentScore"),
        },
        "price": {
            "previous": evaluation.get("previousPrice"),
            "current": evaluation.get("currentPrice"),
        },
        "requiredAction": "JOINT_RESEARCH_RECHECK",
        "researchOnly": True,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }
