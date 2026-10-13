"""RUNLU Scout research agenda and evidence gate.

This module turns a Scout Research Card into a due-diligence agenda and validates
the evidence bundle before joint review can be marked research-complete.

It does not fetch the web and it never changes trading authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


PRIMARY_SOURCE_TYPES = {"REGULATORY_FILING", "COMPANY_IR", "EARNINGS_RELEASE"}
INDEPENDENT_SOURCE_TYPES = {"NEWS", "ANALYST_RESEARCH", "INDUSTRY_SOURCE"}
ALL_SOURCE_TYPES = PRIMARY_SOURCE_TYPES | INDEPENDENT_SOURCE_TYPES


class ResearchEvidenceError(RuntimeError):
    pass


def build_research_agenda(card: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(card.get("symbol") or "").upper()
    if not symbol.endswith(":TSX"):
        raise ResearchEvidenceError("Research agenda requires a TSX Research Card")

    scout = card.get("scout") or {}
    reasons = [str(x) for x in (scout.get("reasons") or [])][:6]
    risks = [str(x) for x in (scout.get("riskFlags") or [])][:6]

    return {
        "symbol": symbol,
        "purpose": "JOINT_DUE_DILIGENCE",
        "questions": [
            "What does the company sell, to whom, and what are the durable revenue drivers?",
            "How have revenue, margins, earnings, free cash flow, and share count changed over recent years?",
            "What is the balance-sheet position, including debt, liquidity, and refinancing risk?",
            "How does current valuation compare with the company's own history and relevant peers?",
            "What is happening in the industry, and who are the strongest competitors?",
            "What has management said recently, and is capital allocation disciplined?",
            "What recent news or catalysts explain the current setup?",
            "What is the strongest bull case?",
            "What is the strongest bear case?",
            "What evidence would prove our thesis wrong?",
            "What concrete condition would invalidate the idea before money is committed?",
        ],
        "scoutContext": {
            "score": scout.get("score"),
            "tier": scout.get("tier"),
            "reasonsToInvestigate": reasons,
            "riskFlagsToChallenge": risks,
        },
        "evidenceRequirements": {
            "minimumSources": 3,
            "minimumPrimarySources": 1,
            "minimumIndependentSources": 1,
            "sourceTypes": sorted(ALL_SOURCE_TYPES),
            "recentNewsPreferredDays": 30,
        },
        "authority": {
            "researchOnly": True,
            "automaticPromotion": False,
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        },
    }


def _parse_date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchEvidenceError("Evidence date must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_evidence_bundle(
    sources: Iterable[Dict[str, Any]],
    *,
    now: datetime | None = None,
) -> Dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    accepted: List[Dict[str, Any]] = []
    errors: List[str] = []
    primary = 0
    independent = 0
    recent_news = 0
    seen_urls = set()

    for index, raw in enumerate(sources):
        if not isinstance(raw, dict):
            errors.append(f"source[{index}] must be an object")
            continue

        source_type = str(raw.get("type") or "").upper()
        title = str(raw.get("title") or "").strip()
        url = str(raw.get("url") or "").strip()
        published = str(raw.get("publishedAt") or "").strip()
        notes = str(raw.get("notes") or "").strip()

        if source_type not in ALL_SOURCE_TYPES:
            errors.append(f"source[{index}] has unsupported type")
            continue
        if not title:
            errors.append(f"source[{index}] title is required")
            continue
        if not (url.startswith("https://") or url.startswith("http://")):
            errors.append(f"source[{index}] URL is invalid")
            continue
        if url in seen_urls:
            errors.append(f"source[{index}] duplicates an existing URL")
            continue
        if not notes:
            errors.append(f"source[{index}] research notes are required")
            continue

        date = None
        if published:
            try:
                date = _parse_date(published)
            except ResearchEvidenceError as exc:
                errors.append(f"source[{index}] {exc}")
                continue
            if date > current:
                errors.append(f"source[{index}] is dated in the future")
                continue

        seen_urls.add(url)
        if source_type in PRIMARY_SOURCE_TYPES:
            primary += 1
        if source_type in INDEPENDENT_SOURCE_TYPES:
            independent += 1
        if source_type == "NEWS" and date is not None:
            if (current - date).days <= 30:
                recent_news += 1

        accepted.append({
            "type": source_type,
            "title": title,
            "url": url,
            "publishedAt": published or None,
            "notes": notes,
        })

    if len(accepted) < 3:
        errors.append("At least three valid research sources are required")
    if primary < 1:
        errors.append("At least one primary company/regulatory source is required")
    if independent < 1:
        errors.append("At least one independent source is required")

    return {
        "complete": not errors,
        "errors": errors,
        "acceptedSources": accepted,
        "sourceCount": len(accepted),
        "primarySourceCount": primary,
        "independentSourceCount": independent,
        "recentNewsCount": recent_news,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }
