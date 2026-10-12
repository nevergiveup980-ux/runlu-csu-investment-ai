"""Build private RUNLU Research Cards from Scout candidates.

Cards are structured research workspaces. They intentionally contain unanswered
questions and cannot promote a stock or authorize a trade.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


REQUIRED_RESEARCH_SECTIONS = (
    "business_model",
    "financial_quality",
    "valuation",
    "industry_and_competition",
    "management_and_governance",
    "recent_news_and_catalysts",
    "bull_case",
    "bear_case",
    "key_risks",
    "what_could_make_us_wrong",
    "invalidation_condition",
)


def build_research_card(candidate: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(candidate.get("symbol") or "").upper()
    if not symbol.endswith(":TSX"):
        raise ValueError("Research Card requires a TSX Scout candidate")

    return {
        "product": "RUNLU Research Card",
        "symbol": symbol,
        "scout": {
            "score": candidate.get("latestScore"),
            "tier": candidate.get("tier"),
            "stage": candidate.get("stage") or "RESEARCH_REQUIRED",
            "reasons": list(candidate.get("reasons") or [])[:8],
            "riskFlags": list(candidate.get("riskFlags") or [])[:8],
            "marketDataAsOf": candidate.get("marketDataAsOf"),
        },
        "research": {
            "business_model": None,
            "financial_quality": None,
            "valuation": None,
            "industry_and_competition": None,
            "management_and_governance": None,
            "recent_news_and_catalysts": None,
            "bull_case": None,
            "bear_case": None,
            "key_risks": [],
            "what_could_make_us_wrong": None,
            "invalidation_condition": None,
            "sources": [],
        },
        "decision": {
            "assistantResearchComplete": False,
            "userConfirmed": False,
            "finalDecision": None,
            "allowedValues": ["PASS", "WATCH", "APPROVED"],
        },
        "authority": {
            "researchRequired": True,
            "realtimeEligible": False,
            "tradeEligible": False,
            "brokerSubmissionEnabled": False,
        },
    }


def card_completion(card: Dict[str, Any]) -> Dict[str, Any]:
    research = card.get("research") or {}
    missing: List[str] = []
    for key in REQUIRED_RESEARCH_SECTIONS:
        value = research.get(key)
        if key == "key_risks":
            if not isinstance(value, list) or not value:
                missing.append(key)
        elif not isinstance(value, str) or not value.strip():
            missing.append(key)

    sources = research.get("sources")
    if not isinstance(sources, list) or len(sources) < 2:
        missing.append("sources_minimum_2")

    complete = not missing
    return {
        "complete": complete,
        "missing": missing,
        "tradeEligible": False,
    }


def build_cards(candidates: Iterable[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    if limit < 1 or limit > 5:
        raise ValueError("Research Card batch limit must be 1-5")
    cards: List[Dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("stage") == "PASS":
            continue
        cards.append(build_research_card(candidate))
        if len(cards) >= limit:
            break
    return cards
