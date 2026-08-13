# RUNLU Webull Bot Trading Policy V2

## Default trading mode

`SWING`

Use `POSITION` for long-term core holdings and `INTRADAY` only when explicitly selected for a specific trade lot.

## Trade-lot discipline

Every purchase is stored as its own trade lot with:
- symbol
- quantity
- entry price
- entry time
- fees
- selected trading mode
- notes / entry thesis

The bot should not erase lot identity by relying only on an average account cost.

## Buy discipline

A BUY may advance only after strategy confirmation, anti-chase checks, conservative position sizing, and account preflight.

Account preflight must confirm sufficient buying power for the estimated order notional before execution can proceed.

## Normal sell discipline

A normal sale requires BOTH:

1. Price protection: current price must be at or above the lot's protected sell floor.
2. Technical confirmation: the configured sell score must reach the threshold for the lot's trading mode.

Default minimum-profit floors:
- INTRADAY: 0.3%
- SWING: 1.5%
- POSITION: 3.0%

These are defaults, not guarantees. Fees/slippage buffers can raise the floor.

Before a SELL may advance, account preflight must also confirm that the requested quantity is actually held.

## Technical sell inputs

The sell gate can consider:
- price vs SMA20
- SMA20 vs SMA50
- RSI14
- MACD vs signal
- relative volume
- proximity to recent resistance

Thresholds:
- INTRADAY: 2 bearish/exit signals
- SWING: 3
- POSITION: 4

A profitable position with a strong trend should remain `HOLD / TRAIL` rather than being sold only because it is above cost.

## Order lifecycle and fill reconciliation

An order is not treated as completed merely because it was submitted. The bot must reconcile broker status until the order reaches a terminal state.

Tracked changes include:
- order status;
- filled quantity;
- partial versus full fill;
- average fill price;
- cancellation/rejection/expiry.

A BUY TradeLot should be created or updated from actual fill data, not from the requested limit price alone.

## Supabase audit trail

Important lifecycle events should be written to the server-side Supabase trade journal, including strategy decisions, preflight results, order previews, submissions, fill changes, TradeLot creation, sell decisions, and closed trades.

The Supabase service-role key must remain server-side and must never be exposed in browser code or committed to GitHub.

## News and earnings layer

A dedicated news + earnings intelligence layer is planned. It should inform BUY/SELL and major-risk-event decisions, but news alone should not bypass execution risk controls.

## Risk override

The no-loss preference is NOT an unlimited-loss rule.

A major risk event may override the normal profit floor and move the lot to `RISK EXIT / REVIEW`. Examples include a severe fundamental break, fraud/accounting event, delisting/solvency risk, or another exceptional event approved by the risk layer.

## Execution policy

V2 remains sandbox-first. Live production trading is not enabled by this policy.
