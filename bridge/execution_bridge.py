"""Dry-run execution bridge for CSU Bot V2.

This module intentionally cannot submit brokerage orders. It validates an already
approved/preflighted order payload and produces a redacted request envelope for
operator review. The existing read-only bridge remains separate and untouched.

Live submission is deliberately absent until trading authorization, approval
persistence, fresh quote sourcing, signing, and reconciliation are verified.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from approval_ledger import DEFAULT_LEDGER, ApprovalLedgerError, proposal_digest as stored_proposal_digest, proposal_status

SNAPTRADE_PLACE_ORDER_URL = "https://api.snaptrade.com/trade/place"
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)


class ExecutionBridgeError(ValueError):
    pass


@dataclass(frozen=True)
class DryRunEnvelope:
    mode: str
    method: str
    url: str
    body: Dict[str, Any]
    network_sent: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "method": self.method,
            "url": self.url,
            "body": self.body,
            "network_sent": self.network_sent,
        }


def validate_order_body(body: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(body, dict):
        raise ExecutionBridgeError("Order body must be an object")

    allowed = {
        "account_id",
        "action",
        "universal_symbol_id",
        "symbol",
        "order_type",
        "time_in_force",
        "trading_session",
        "price",
        "stop",
        "units",
        "notional_value",
        "client_order_id",
    }
    extras = sorted(set(body) - allowed)
    if extras:
        raise ExecutionBridgeError(f"Unexpected order fields: {', '.join(extras)}")

    account_id = str(body.get("account_id") or "")
    if not account_id:
        raise ExecutionBridgeError("Private account_id is required at runtime")

    if body.get("action") not in ("BUY", "SELL"):
        raise ExecutionBridgeError("Only BUY or SELL is allowed")
    if body.get("symbol") != "CSU.TO" or body.get("universal_symbol_id") is not None:
        raise ExecutionBridgeError("Only brokerage symbol CSU.TO is allowed")
    if body.get("order_type") != "Limit":
        raise ExecutionBridgeError("Only Limit orders are allowed")
    if body.get("time_in_force") != "Day":
        raise ExecutionBridgeError("Only Day orders are allowed")
    if body.get("trading_session") != "REGULAR":
        raise ExecutionBridgeError("Only regular-hours orders are allowed")
    if body.get("units") != 1 or body.get("notional_value") is not None:
        raise ExecutionBridgeError("Exactly one share is required")
    if body.get("stop") is not None:
        raise ExecutionBridgeError("Stop price must be null for a plain Limit order")

    price = body.get("price")
    if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
        raise ExecutionBridgeError("Limit price must be positive")

    client_order_id = str(body.get("client_order_id") or "")
    if not UUID_RE.match(client_order_id):
        raise ExecutionBridgeError("client_order_id must be a canonical UUID")

    return {
        "account_id": account_id,
        "action": body["action"],
        "universal_symbol_id": None,
        "symbol": "CSU.TO",
        "order_type": "Limit",
        "time_in_force": "Day",
        "trading_session": "REGULAR",
        "price": float(price),
        "stop": None,
        "units": 1,
        "notional_value": None,
        "client_order_id": client_order_id,
    }


def execution_order_digest(order_body: Dict[str, Any]) -> str:
    normalized = validate_order_body(order_body)
    reviewable = dict(normalized)
    reviewable.pop("account_id", None)
    payload = json.dumps(reviewable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_dry_run(order_body: Dict[str, Any]) -> DryRunEnvelope:
    normalized = validate_order_body(order_body)
    # Never log or return a real brokerage account identifier.
    review_body = dict(normalized)
    review_body["account_id"] = "[PRIVATE_RUNTIME_ACCOUNT]"
    return DryRunEnvelope(
        mode="DRY_RUN_ONLY",
        method="POST",
        url=SNAPTRADE_PLACE_ORDER_URL,
        body=review_body,
        network_sent=False,
    )


def build_approved_dry_run(
    order_body: Dict[str, Any],
    *,
    ledger_path: Path = DEFAULT_LEDGER,
) -> DryRunEnvelope:
    normalized = validate_order_body(order_body)
    try:
        status = proposal_status(normalized["client_order_id"], ledger_path)
    except ApprovalLedgerError as exc:
        raise ExecutionBridgeError("Approval ledger validation failed") from exc
    if status.get("state") != "APPROVED":
        raise ExecutionBridgeError("Proposal is not approved in the local audit ledger")
    try:
        approved_digest = stored_proposal_digest(normalized["client_order_id"], ledger_path)
    except ApprovalLedgerError as exc:
        raise ExecutionBridgeError("Approved proposal digest is unavailable") from exc
    actual_digest = execution_order_digest(normalized)
    if not hmac.compare_digest(approved_digest, actual_digest):
        raise ExecutionBridgeError("Approved proposal no longer matches the order body")
    return build_dry_run(normalized)


def submit_live(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError(
        "Live brokerage submission is intentionally disabled in this bridge version"
    )


def main() -> None:
    import sys

    raw = json.load(sys.stdin)
    envelope = build_approved_dry_run(raw)
    json.dump(envelope.as_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
