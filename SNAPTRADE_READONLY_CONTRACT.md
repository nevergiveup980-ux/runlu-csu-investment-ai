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
