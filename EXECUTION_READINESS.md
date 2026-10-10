# CSU Bot — controlled execution readiness (not live trading)

Official SnapTrade docs: https://docs.snaptrade.com/docs/trading-with-snaptrade
Broker support: https://docs.snaptrade.com/docs/broker-access-guide
Personal API quickstart: https://docs.snaptrade.com/docs/getting-started

## Verified facts (2026-10)
- SnapTrade lists **Webull CA** as **Read and Trade** at the integration level.
- This does **not** establish that this user's existing connection, account, or
  Personal API key has trading privileges. Inspect authorization type and account
  capabilities separately.
- Personal API keys can trade where enabled. Personal API requests omit
  `userId` and `userSecret`.
- An existing read-only authorization must be reauthorized with
  `reconnect=<existing connection ID>` and `connectionType=trade` using the
  official Generate Connection Portal URL operation, if the user opts in.
- Standard equity order endpoint: `POST /trade/place`; checking impact and
  placing a checked trade are alternative documented operations. These are
  **not implemented** in this branch.

## Safety boundary
- Existing local `server.py` and `bridge.py` remain GET-only and read-only.
- Do not send Personal API keys, raw snapshots, or account identifiers to the
  public GitHub repo or static Pages site.
- `execution_readiness.py` is a pure offline diagnostic. It never calls a broker.
- The authenticated proposal endpoint creates only a reviewable limit-order
  proposal, never an order. Do not label it an actual approval/execution system.
- Any future execution service must be localhost-only or otherwise strongly
  authenticated, separate from the public site, with deliberate human approval,
  expiry, one-shot order IDs, idempotency, durable audit log, and post-submission
  reconciliation. If order state is ambiguous, stop rather than retry.
- No margin, short selling, options, or automatic cancellation; 3 CSU shares
  maximum and 1 share per order.
- Check market-data age separately from account-snapshot age. Daily Yahoo
  research candles are **not** sufficient to price live intraday orders.
- Treat price limit, fees, spread, market hours, cash buffer, and pending orders
  as hard pre-submission checks.
- Until the above is verified, all execution remains OFF.
