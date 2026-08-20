from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
import sys
import uuid

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

from order_guard import OrderIntent, OrderRejected, validate_order


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_client() -> TradeClient:
    app_key = required("WEBULL_APP_KEY")
    app_secret = required("WEBULL_APP_SECRET")
    api_client = ApiClient(app_key, app_secret, "us")
    # Hard lock: V2 has no production host path.
    api_client.add_endpoint("us", "api.sandbox.webull.com")
    return TradeClient(api_client)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or place a guarded US equity LIMIT order in Webull Sandbox."
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", required=True, choices=["BUY", "SELL"])
    parser.add_argument("--quantity", required=True, type=Decimal)
    parser.add_argument("--limit-price", required=True, type=Decimal)
    parser.add_argument(
        "--execute-sandbox",
        action="store_true",
        help="Actually submit to Webull Sandbox. Without this flag the script only previews.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    intent = OrderIntent(
        symbol=args.symbol.upper(),
        side=args.side.upper(),
        quantity=args.quantity,
        limit_price=args.limit_price,
    )

    try:
        approval = validate_order(intent, environment="sandbox")
    except OrderRejected as exc:
        print(json.dumps({"approved": False, "error": str(exc)}, indent=2))
        sys.exit(2)

    preview = {
        "mode": "SANDBOX_EXECUTE" if args.execute_sandbox else "PREVIEW_ONLY",
        "risk_check": approval,
        "broker_call_made": False,
    }

    if not args.execute_sandbox:
        print(json.dumps(preview, indent=2))
        return

    # Second independent arming gate. A CLI flag alone can never submit an order.
    if os.getenv("RUNLU_SANDBOX_TRADING_ARMED", "").strip() != "YES":
        preview["blocked"] = (
            "Set RUNLU_SANDBOX_TRADING_ARMED=YES only when you intentionally want "
            "to submit a sandbox order."
        )
        print(json.dumps(preview, indent=2))
        sys.exit(3)

    account_id = required("WEBULL_ACCOUNT_ID")
    client = build_client()
    client_order_id = uuid.uuid4().hex[:32]
    new_orders = [
        {
            "combo_type": "NORMAL",
            "client_order_id": client_order_id,
            "symbol": intent.symbol,
            "instrument_type": "EQUITY",
            "market": "US",
            "order_type": "LIMIT",
            "limit_price": str(intent.limit_price),
            "quantity": str(intent.quantity),
            "support_trading_session": "CORE",
            "side": intent.side,
            "time_in_force": "DAY",
            "entrust_type": "QTY",
        }
    ]

    response = client.order_v3.place_order(account_id, new_orders)
    result = {
        **preview,
        "broker_call_made": True,
        "client_order_id": client_order_id,
        "status_code": response.status_code,
    }
    try:
        result["response"] = response.json()
    except Exception:
        result["response"] = response.text[:1000]

    print(json.dumps(result, indent=2))
    if response.status_code != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
