# CSU Bot V2 — Experimental Trader

This branch upgrades the CSU research robot into a **three-share experimental decision system** while keeping real order execution disabled.

## Strategy

**Adaptive Swing Trader**

- 1 Core share — patient base position.
- 1 Swing share — normal multi-day / multi-week trading.
- 1 Reserve share — unlocked only by a higher-quality setup.
- Cash is a valid position.
- The bot is not required to trade every day.
- Intraday trading is not the primary strategy.

## Safety boundary

The hard authorization ceiling is **3 shares**. One preview action may change position by at most **1 share**.

The current branch does **not** place, modify, or cancel live orders. Margin, shorting, options, and leverage are outside the experiment.

A separate Risk Engine validates every proposed action before it can be considered for any future broker execution layer.

## API

- `GET /api/bot/status` — strategy and safety state.
- `GET /api/bot/preview?shares=0&cash=9000` — calculate a paper-only decision using current CSU market indicators.
- Existing CSU research endpoint remains available at `GET /api/csu`.

## Next broker milestone

SnapTrade/Webull work should attach through the read-only broker boundary first:

1. connection health
2. account/cash
3. CSU position and average cost
4. open orders
5. transaction history
6. only after validation: a separately reviewed human-approved order workflow

Real credentials belong in local secrets / deployment secrets only and must never be committed.
