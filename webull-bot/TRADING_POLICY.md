# RUNLU Webull Bot Trading Policy V2

## Default trading mode

`SWING`

Use `POSITION` for long-term core holdings and `INTRADAY` only when explicitly selected for a specific trade lot.

## Buy discipline

A BUY is never created from a single indicator. The buy gate first classifies the setup as `BUY CANDIDATE`, `WATCH`, or `BLOCK`.

The gate can consider:
- price vs SMA20
- SMA20 vs SMA50
- RSI14
- MACD vs signal
- distance from 20-period support
- room to recent resistance
- relative volume

Anti-chase protection is a hard gate. A setup is blocked when price is excessively extended above SMA20 for the selected trading mode.

Default maximum SMA20 premiums:
- INTRADAY: 5%
- SWING: 6%
- POSITION: 4%

Default confirmation thresholds:
- INTRADAY: 4 points
- SWING: 4 points
- POSITION: 5 points

POSITION mode is intentionally more selective. `SWING` remains the default.

## Position sizing

A qualifying setup still does not determine order size by itself. The sizing layer must respect both:
- a maximum percentage of currently available cash allocated to the new trade; and
- a maximum share quantity.

The V2 helper defaults to conservative preview behavior and may return quantity `0` when the cash cap cannot support even one share. Sizing output is an order plan only; it does not place an order.

## Trade-lot discipline

Every completed purchase is stored as its own trade lot with:
- symbol
- quantity
- entry price
- entry time
- fees
- selected trading mode
- notes / entry thesis

The bot should not erase lot identity by relying only on an average account cost.

## Normal sell discipline

A normal sale requires BOTH:

1. Price protection: current price must be at or above the lot's protected sell floor.
2. Technical confirmation: the configured sell score must reach the threshold for the lot's trading mode.

Default minimum-profit floors:
- INTRADAY: 0.3%
- SWING: 1.5%
- POSITION: 3.0%

These are defaults, not guarantees. Fees/slippage buffers can raise the floor.

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

## Risk override

The no-loss preference is NOT an unlimited-loss rule.

A major risk event may override the normal profit floor and move the lot to `RISK EXIT / REVIEW`. Examples include a severe fundamental break, fraud/accounting event, delisting/solvency risk, or another exceptional event approved by the risk layer.

## End-to-end lifecycle

`market data -> buy gate -> sizing plan -> order intent -> risk guard -> user approval -> sandbox broker adapter -> fill reconciliation -> TradeLot -> monitoring -> sell gate -> order intent`

The buy gate, sizing layer, sell gate, and broker adapter remain separate so that strategy logic cannot bypass execution controls.

## Execution policy

V2 remains sandbox-first. Live production trading is not enabled by this policy.
