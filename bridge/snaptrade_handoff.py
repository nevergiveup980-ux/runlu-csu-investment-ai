#!/usr/bin/env python3
"""
Local-only handoff adapter for the already-working CSU SnapTrade bridge.

This file never authenticates to SnapTrade and contains no broker write methods.
It accepts a sanitized snapshot from the local reader and forwards it to CSU Bot
V2's read-only simulation endpoint.
"""
import json
import os
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

BOT_URL = os.getenv("CSU_BOT_ACCOUNT_PREVIEW_URL", "http://127.0.0.1:8787/api/bot/account-preview")
SNAPSHOT_CACHE = Path(".csu-private") / "latest-snapshot.json"


def sanitize_snapshot(raw):
    """Whitelist only fields the bot needs. Secrets are intentionally discarded."""
    positions = []
    for p in raw.get("positions") or []:
        positions.append({
            "symbol": p.get("symbol") or p.get("ticker") or "",
            "quantity": p.get("quantity") or p.get("units") or 0,
            "averageCost": p.get("averageCost") or p.get("average_cost"),
            "marketValue": p.get("marketValue") or p.get("market_value"),
        })

    orders = []
    for o in raw.get("openOrders") or raw.get("orders") or []:
        orders.append({
            "id": o.get("id") or o.get("orderId"),
            "symbol": o.get("symbol") or o.get("ticker") or "",
            "side": str(o.get("side") or o.get("action") or "UNKNOWN").upper(),
            "quantity": o.get("quantity") or o.get("units") or 0,
            "limitPrice": o.get("limitPrice") or o.get("limit_price") or o.get("price"),
            "status": o.get("status") or "OPEN",
        })

    transactions = []
    for t in raw.get("transactions") or raw.get("history") or []:
        transactions.append({
            "id": t.get("id"),
            "symbol": t.get("symbol") or t.get("ticker"),
            "side": t.get("side") or t.get("action"),
            "quantity": t.get("quantity") or t.get("units"),
            "price": t.get("price"),
            "date": t.get("date") or t.get("trade_date"),
            "type": t.get("type"),
        })

    return {
        "provider": raw.get("provider") or "SnapTrade / Webull Canada",
        "accountId": raw.get("accountId") or raw.get("account_id"),
        "currency": raw.get("currency") or "CAD",
        "cash": raw.get("cash"),
        "buyingPower": raw.get("buyingPower") if raw.get("buyingPower") is not None else raw.get("buying_power"),
        "positions": positions,
        "openOrders": orders,
        "transactions": transactions,
        "fetchedAt": raw.get("fetchedAt") or raw.get("fetched_at"),
    }


def cache_sanitized_snapshot(raw, path=SNAPSHOT_CACHE):
    """Atomically cache only the sanitized snapshot in the gitignored private area."""
    safe = sanitize_snapshot(raw)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="snapshot-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(safe, handle, separators=(",", ":"), ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return safe


def _auth_headers():
    token = os.getenv("CSU_SNAPSHOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("CSU_SNAPSHOT_TOKEN is required for private bot endpoints")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def forward_snapshot(raw):
    safe = sanitize_snapshot(raw)
    payload = json.dumps(safe).encode("utf-8")
    req = urllib.request.Request(
        BOT_URL,
        data=payload,
        headers=_auth_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"CSU Bot rejected snapshot: HTTP {exc.code}: {body[:500]}") from exc


if __name__ == "__main__":
    # Pipe the existing reader's sanitized JSON here:
    #   python snapshot_reader.py | python snaptrade_handoff.py
    raw = json.load(__import__("sys").stdin)
    result = forward_snapshot(raw)
    print(json.dumps(result, indent=2))
