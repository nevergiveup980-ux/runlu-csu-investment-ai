import json
import os
import sys

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def sanitize_accounts(payload):
    """Return only non-secret account metadata for a connection smoke test."""
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("data") or payload.get("accounts") or [payload]
    else:
        return {"connected": True, "account_count": None}

    safe = []
    for item in rows if isinstance(rows, list) else []:
        if not isinstance(item, dict):
            continue
        safe.append({
            "account_id": item.get("account_id") or item.get("accountId") or item.get("id"),
            "account_type": item.get("account_type") or item.get("accountType") or item.get("type"),
            "status": item.get("status"),
        })
    return {"connected": True, "account_count": len(safe), "accounts": safe}


def main():
    app_key = required("WEBULL_APP_KEY")
    app_secret = required("WEBULL_APP_SECRET")

    # V1.0 intentionally hard-locks to Webull Sandbox.
    api_client = ApiClient(app_key, app_secret, "us")
    api_client.add_endpoint("us", "api.sandbox.webull.com")
    trade_client = TradeClient(api_client)

    response = trade_client.account_v2.get_account_list()
    if response.status_code != 200:
        print(json.dumps({"connected": False, "status_code": response.status_code, "error": response.text[:500]}, indent=2))
        sys.exit(1)

    print(json.dumps(sanitize_accounts(response.json()), indent=2))


if __name__ == "__main__":
    main()
