# RUNLU CSU Investment AI V1.0

A read-only research dashboard for **Constellation Software Inc. (TSX: CSU)**.

## V1 core

- Daily / 1H / 15m / 5m market views
- SMA20 / SMA50
- RSI14
- MACD + signal
- ATR14
- 20-period support / resistance
- Relative volume
- Rule-based stance: Bullish / Neutral / Caution

## Architecture

- GitHub stores the project and static dashboard.
- Cloudflare Worker securely calls the market-data provider.
- `TWELVE_DATA_API_KEY` must be stored as a Cloudflare secret and must never be committed to GitHub.
- V1 is research-only and never places trades.

## Deployment

The static dashboard can be published with GitHub Pages. Live CSU data is supplied by the Cloudflare Worker API.
