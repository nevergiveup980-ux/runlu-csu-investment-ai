# Project 200 — first real-data research protocol

**RESEARCH / PAPER ONLY.** This is not a trading recommendation or permission to route live orders.

## Data acquisition

Preferred starting instrument: one liquid US-listed ETF such as SPY, using a provider and license suitable for the intended private research. Confirm the instrument's exact ticker and currency. Do not commit API keys, licensed raw market data, or provider credentials.

Alpha Vantage documents `TIME_SERIES_DAILY` raw OHLCV and `TIME_SERIES_DAILY_ADJUSTED` corporate-action fields. **The free compact response contains only the most recent 100 daily bars**; the current Project 200 default requires **at least 120 bars**, so compact alone is insufficient. Full daily history requires the provider's premium entitlement. Obtain the permitted file through your own account and save it locally. Do not mislabel synthetic or demo data as market observations.

The local adapter accepts a JSON response from `TIME_SERIES_DAILY`:
```sh
cd project200
python alphavantage_daily_adapter.py /path/to/provider_daily.json /path/to/SPY_raw.csv
python run_research_bundle.py /path/to/SPY_raw.csv --source-label 'Alpha Vantage / SPY / raw daily / acquisition date YYYY-MM-DD' --output /path/to/spy_bundle.json
python -m unittest discover -v -p 'test_*.py'
```

The adapter does **not** fetch from the network. It rejects provider error messages, malformed prices, invalid OHLC relationships, and overwriting the input. The research bundle verifies the input SHA-256, computes held-out results, a 9-scenario cost grid, and an evidence screen.

## Required manual checks before interpreting a report

1. Confirm license, symbol, trading currency, exchange calendar, timestamp convention, and acquisition date.
2. Check for missing sessions, splits, dividends, delistings, and data revisions. The raw daily adapter does not adjust corporate actions.
3. Ensure the input has at least 120 valid daily bars and a meaningful held-out period. **A 100-bar compact response must fail** the default research gate.
4. Keep the held-out test untouched during strategy tuning; if you tune on it, label it exploratory and create a new future test period.
5. Confirm actual fees, FX costs, taxes, spreads, order size constraints, liquidity, and broker eligibility separately.
6. Do not extrapolate daily-bar backtests to intraday trading. Daily bars cannot establish stop execution, latency, or actual slippage.
7. Archive code commit, source metadata, SHA-256, assumptions, and JSON report; do not publish provider data unless authorized.

A passing evidence screen is **not** proof of profitable trading. Project 200 has no authorized live order route and no verified real profit.
