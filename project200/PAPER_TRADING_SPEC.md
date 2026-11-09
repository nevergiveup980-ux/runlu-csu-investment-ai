# Project 200 — USD Paper Trading Specification (v0.1)

Status: DESIGN / PAPER ONLY. No live brokerage permissions or orders.

## Mandate
- Reference capital: USD 2,000. This is a challenge allocation, NOT authority to access all Webull funds.
- Aspirational monthly net P&L: USD 200 (10%); no return guarantee or forced daily quota.
- Universe: liquid US-listed stocks and ETFs, with CAD-listed securities only after FX/cost accounting.
- Cash-only, long-only in phase 1. No leverage, short sales, uncovered options, or derivatives with uncapped losses.
- Strategy candidates: intraday momentum and 1–5 day swing; no execution before validation.

## Hard pretrade checks (fail closed)
1. Environment must be PAPER; any live mode is rejected.
2. Use a dedicated virtual USD 2,000 subledger; never infer challenge funds from total broker buying power.
3. Reject orders exceeding available settled cash, duplicate client order IDs, stale prices, halted securities, and illiquid symbols.
4. Planned risk per trade <= USD 20 based on entry and stop; max gross exposure <= USD 1,800; retain >= USD 200 cash.
5. Daily realized plus unrealized drawdown >= USD 40: halt new orders for the session.
6. Cumulative drawdown from USD 2,000 initial capital >= USD 200: halt and require review.
7. Stop orders do not guarantee a fill at stop price; gaps and outages can exceed limits.
8. Include commissions, regulatory fees, spread, slippage, FX and financing in net P&L.
9. Maintain immutable event log: timestamps, symbol, side, qty, order id, quote age, fills, fees, rejection reasons, cash, positions, equity.

## Validation gates
- Verify broker account type, USD balance, market data rights, API permissions, order types and settlement restrictions.
- Backtest with out-of-sample and walk-forward segments, conservative transaction costs, and no lookahead.
- Paper trade at least 20 trading sessions, including realistic fills and failures.
- Report net P&L, max drawdown, hit rate, average win/loss, profit factor, turnover, and exposure.
- Any proposed live activation is a separate security review and explicit authorization. Do not change existing read-only SnapTrade connection.

## Operational status
No actual broker orders placed. No account balances verified in this specification. No profitability demonstrated.
