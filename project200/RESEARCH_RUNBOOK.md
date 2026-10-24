# Project 200 — reproducible offline research

This repository is **PAPER / RESEARCH ONLY**. No live order route exists.

1. Obtain properly licensed **daily** OHLCV for a selected ticker from an authorized provider. Confirm adjustments for splits/dividends and the provider's rights/limits.
2. Prepare CSV with exactly `date,open,high,low,close,volume` (ISO dates, ascending, at least 120 bars). Twelve Data responses can be converted with `twelvedata_adapter.convert()`.
3. From `project200/` run:
   `python -m unittest discover -v -p 'test_*.py'`
   `python run_research.py path/to/SPY.csv --output spy_report.json`
4. Archive the input CSV (where license permits), SHA-256, code commit, parameter assumptions, and JSON report. **Never commit API keys.**
5. Compare held-out results with cash baseline. Do not use the held-out segment to tune parameters and then call it untouched.
6. No evidence of profitability until a real, independently sourced dataset has been processed and results verified.

Caveats: daily bar data cannot validate intraday fills or stops; split/dividend handling is not verified; the report drawdown is based on closed trades only; the initial backtest has simplified position sizing and cost assumptions. The strategy is not approved for live trading.
