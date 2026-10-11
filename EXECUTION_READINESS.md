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
- The trading guide describes requesting trading permissions using `connectionType=trade` and an existing connection ID. The Connection Portal guide describes `reconnect` primarily for disabled connections. Do not automate reauthorization or assume that upgrading an active read-only connection is accepted without verifying the flow with SnapTrade and the account owner.
- Standard equity order endpoint: `POST /trade/place`; checking impact and placing a checked trade are alternative documented operations. SnapTrade recommends the brokerage `symbol` for typical equity workflows, so the CSU preflight now emits `symbol: "CSU.TO"` and `universal_symbol_id: null`. Live submission is **not implemented** in this branch.

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

## Lifecycle implementation (offline only)
- `src/order-lifecycle.ts` models PROPOSED -> APPROVED -> SUBMISSION_UNKNOWN -> BROKER_ACCEPTED -> FILLED/CANCELLED/REJECTED.
- A submission attempt enters SUBMISSION_UNKNOWN before any hypothetical network request; ambiguous outcomes must be reconciled, never blindly retried.
- `src/order-lifecycle.test.ts` is a regression test source; it must be executed by CI before claiming its checks passed.
- No endpoint currently performs approval, durable persistence, or broker execution. This is a pure state machine only.

## Dry-run execution bridge
- `bridge/execution_bridge.py` validates the final SnapTrade equity-order shape and emits a redacted review envelope only.
- It accepts only CSU.TO, one share, Limit, Day, REGULAR session, positive price, canonical UUID `client_order_id`, and a runtime account ID.
- The account ID is redacted from review output.
- `submit_live()` intentionally raises; there is no broker network write path in this version.
- `bridge/test_execution_bridge.py` verifies that market orders, other symbols, multi-share orders, and live submission are blocked.
