"""Generate a CSU human-review candidate from a private snapshot and push it locally.

This module calls only the bot's proposal endpoint and the localhost review
panel. It cannot place, modify, or cancel brokerage orders.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from bot_review_hook import publish_review_response
from snaptrade_handoff import _auth_headers, sanitize_snapshot

PROPOSAL_URL = os.getenv(
    "CSU_BOT_TRADE_PROPOSAL_URL",
    "http://127.0.0.1:8787/api/bot/trade-proposal",
)


class ReviewCandidateError(RuntimeError):
    pass


def request_review_candidate(
    raw_snapshot: Dict[str, Any],
    *,
    indicative_limit_cad: float,
    expires_at: str,
    url: str = PROPOSAL_URL,
) -> Dict[str, Any]:
    if not isinstance(indicative_limit_cad, (int, float)) or indicative_limit_cad <= 0:
        raise ReviewCandidateError("Indicative limit must be positive")
    safe = sanitize_snapshot(raw_snapshot)
    payload = json.dumps({
        "snapshot": safe,
        "limitPriceCAD": float(indicative_limit_cad),
        "expiresAt": expires_at,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers=_auth_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ReviewCandidateError(
            f"CSU Bot rejected review candidate: HTTP {exc.code}: {body[:300]}"
        ) from exc
    except Exception as exc:
        raise ReviewCandidateError("Unable to reach CSU Bot proposal endpoint") from exc
    if not isinstance(result, dict):
        raise ReviewCandidateError("CSU Bot returned invalid JSON")
    return result


def request_and_publish_review(
    raw_snapshot: Dict[str, Any],
    *,
    indicative_limit_cad: float,
    expires_at: str,
) -> Dict[str, Any]:
    result = request_review_candidate(
        raw_snapshot,
        indicative_limit_cad=indicative_limit_cad,
        expires_at=expires_at,
    )
    if result.get("reviewPacket") is None:
        return {
            "published": False,
            "reason": "Bot produced no reviewable BUY/SELL proposal",
            "decision": (result.get("decision") or {}).get("action"),
        }
    panel = publish_review_response(result)
    return {
        "published": True,
        "proposal_id": result["reviewPacket"].get("proposalId"),
        "panel": panel,
        "broker_submission_enabled": False,
    }
