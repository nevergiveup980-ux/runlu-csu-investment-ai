# RUNLU CSU Investment AI — CSU Bot V2

A CSU-focused research and experimental trading assistant for **Constellation Software Inc. (TSX: CSU)**.

## V2 direction

The robot now has a **three-share experimental architecture**:

- 1 Core share
- 1 Swing share
- 1 Reserve share
- Adaptive Swing strategy
- Cash is a valid position
- No requirement to trade every day
- Intraday trading is secondary, not the primary strategy

## Safety first

This branch is still **PAPER / PREVIEW ONLY**.

- Maximum authorized position: 3 shares
- Maximum proposed change per decision: 1 share
- No shorting
- No margin / leverage
- No options
- No live order placement
- No order modification or cancellation
- Risk Engine checks every proposed action
- Kill Switch remains armed

## API

- `GET /api/health`
- `GET /api/csu`
- `GET /api/bot/status`
- `GET /api/bot/preview?shares=1&cash=6000`

The preview endpoint uses current CSU indicators to generate a paper-only BUY / SELL / HOLD decision.

## Broker roadmap

The broker layer is intentionally separated from the strategy layer. The next milestone is a read-only SnapTrade/Webull connection for account health, cash, positions, open orders and history.

Real credentials must never be committed. Local secret values belong in `.env.local` or deployment secrets. `.env.example` contains placeholders only.

See `CSU_BOT_V2.md` for the strategy and safety design.
