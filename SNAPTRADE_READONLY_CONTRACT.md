# Read-Only Snapshot Contract

CSU Bot V2 deliberately does not own broker credentials. The already-working Webull Canada → SnapTrade reader should publish only a sanitized account snapshot to the bot boundary.

## Preferred JSON

```json
{
  "provider": "SnapTrade / Webull Canada",
  "currency": "CAD",
  "cash": 9895.53,
  "buyingPower": 7045.53,
  "positions": [
    {
      "symbol": "CSU.TO",
      "quantity": 0,
      "averageCost": null
    }
  ],
  "openOrders": [
    {
      "id": "redacted-or-provider-id",
      "symbol": "CSU.TO",
      "side": "BUY",
      "quantity": 1,
      "limitPrice": 2850,
      "status": "OPEN"
    }
  ],
  "transactions": [
    { "symbol": "CSU.TO", "side": "BUY", "quantity": 1, "price": 0, "date": "..." }
  ],
  "fetchedAt": "ISO-8601 timestamp"
}
```

The example numbers document the verified checkpoint only. Runtime data must come from the reader.

## Rules

1. Never include SnapTrade client secrets, user secrets, Webull credentials, tokens, cookies, or authorization headers.
2. Preserve broker order IDs only if needed for read-only reconciliation; otherwise redact them.
3. Normalize CSU symbols to CSU / CSU.TO / CSU:TSX.
4. Preserve all open orders so the bot can reserve both share slots and funds.
5. Use broker buying power as deployable cash.
6. If the snapshot is stale, malformed, or unavailable, the bot must fail closed to HOLD / NO TRADE.
7. No code in the snapshot publisher may place, replace, modify, or cancel orders.


## Existing local bridge integration

The previously validated local bridge runs with `python3 server.py` and serves the dashboard at `http://127.0.0.1:8765`.

V2 includes `bridge/local_bridge_hook.py`. The existing server should call `publish_to_csu_bot(dashboard_payload)` **after** it has assembled the sanitized read-only account/dashboard payload. The hook whitelists the fields through `snaptrade_handoff.py` and POSTs them to `/api/bot/account-preview`.

No SnapTrade authentication code is duplicated in V2. No credentials cross this boundary. No broker order endpoint is called.

The local bridge source itself is not stored in this GitHub repository, so the exact one-line hook cannot be inserted into `server.py` from this branch until that local source is available to the runtime. The integration contract and receiving endpoint are complete.
