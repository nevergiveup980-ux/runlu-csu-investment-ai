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

## Execution policy

V2 remains sandbox-first. Live production trading is not enabled by this policy.
