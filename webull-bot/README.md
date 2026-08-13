# RUNLU Webull Bot V2 — Trading Readiness

A sandbox-first Webull OpenAPI integration that prepares RUNLU Investment AI for a future user-confirmed US-stock execution workflow.

## What changed in V2

V2 adds a real order-execution scaffold, but it remains hard-locked to Webull Sandbox. It can now:

- connect to the Webull Sandbox account;
- evaluate a mode-aware BUY gate before any order intent exists;
- reject price-chasing setups that are excessively extended above SMA20;
- create a conservative position-sizing plan from available cash and quantity caps;
- store each completed purchase as an independent TradeLot;
- evaluate a protected SELL gate with minimum-profit floors and technical confirmation;
- build a US equity LIMIT order using Webull's official `order_v3.place_order` SDK method;
- validate every order through a separate risk guard before any broker call;
- preview an order without touching Webull;
- submit a sandbox order only after two independent arming steps;
- run automated buy/sell/guard tests in GitHub Actions.

## Default trading discipline

Default mode: `SWING`.

Other modes are available per TradeLot:
- `POSITION` — more selective entry and exit thresholds for longer-term holdings;
- `SWING` — default mode for multi-day / multi-week opportunities;
- `INTRADAY` — available only when explicitly selected for a trade lot.

The bot does not treat “price is up” as a sell reason by itself and does not treat “price is down” as a buy reason by itself.

## Buy Gate

A setup is classified as `BUY CANDIDATE`, `WATCH`, or `BLOCK` using multiple inputs such as SMA20/SMA50, RSI14, MACD, support, resistance and relative volume.

A hard anti-chase rule blocks entries that are too far above SMA20 for the selected trading mode.

Even a `BUY CANDIDATE` does not place an order. It passes to the sizing and order-intent layers first.

## Position sizing

The sizing helper respects both available cash and configured quantity caps. It may return quantity `0` if the configured cash allocation cannot support one share.

## TradeLot + Sell Gate

Each completed buy becomes its own TradeLot with entry price, quantity, time, fees, trading mode and notes. Normal sells are evaluated against that lot's break-even/protected floor rather than relying only on an account-wide average cost.

A normal sale requires both:
1. price protection; and
2. sufficient technical sell confirmation.

A separate major-risk-event override prevents the no-loss preference from becoming an unlimited-loss rule.

See `TRADING_POLICY.md` for the full policy.

## Safety architecture

V2 deliberately rejects:

- production/live endpoints;
- symbols not listed in `RUNLU_ALLOWED_SYMBOLS`;
- short selling;
- market orders;
- extended-hours orders;
- non-US markets;
- non-equity instruments;
- quantities or notionals above configured limits.

A command-line flag by itself is not sufficient to submit an order. Sandbox execution also requires `RUNLU_SANDBOX_TRADING_ARMED=YES`.

**There is no production host path in V2. Real-money execution is not enabled.**

## Required secrets for account connection

- `WEBULL_APP_KEY`
- `WEBULL_APP_SECRET`

For sandbox order submission:

- `WEBULL_ACCOUNT_ID`
- Webull access-token configuration if required by the account / 2FA setup

Never commit credentials to this repository. Store them in environment variables, Cloudflare secrets, Supabase Vault where appropriate, or GitHub Actions Secrets.

## Risk-control environment variables

- `RUNLU_ALLOWED_SYMBOLS` — comma-separated explicit allowlist, for example `AAPL,MSFT`
- `RUNLU_MAX_ORDER_QTY` — maximum shares per order; default `1`
- `RUNLU_MAX_ORDER_NOTIONAL` — maximum estimated order value; default `1000`
- `RUNLU_SANDBOX_TRADING_ARMED` — must equal exactly `YES` for an actual sandbox submission

An empty symbol allowlist blocks every order.

## Connection smoke test

```bash
pip install -r webull-bot/requirements.txt
python webull-bot/src/sandbox_check.py
```

## Safe order preview

This performs validation only and makes no broker call:

```bash
export RUNLU_ALLOWED_SYMBOLS=AAPL
export RUNLU_MAX_ORDER_QTY=1
export RUNLU_MAX_ORDER_NOTIONAL=1000
python webull-bot/src/sandbox_order.py \
  --symbol AAPL --side BUY --quantity 1 --limit-price 180
```

## Intentional sandbox submission

Only after the preview is correct and Webull Sandbox credentials are configured:

```bash
export RUNLU_SANDBOX_TRADING_ARMED=YES
python webull-bot/src/sandbox_order.py \
  --symbol AAPL --side BUY --quantity 1 --limit-price 180 \
  --execute-sandbox
```

The runner always uses `api.sandbox.webull.com`.

## Planned path toward future execution

1. Sandbox connection and account discovery — built
2. Buy Gate + anti-chase discipline — built
3. Conservative position sizing — built
4. TradeLot identity + protected Sell Gate — built
5. Independent order risk guard — built
6. Dry-run / order preview — built
7. Guarded sandbox order placement — built
8. Balance + positions pre-trade checks
9. Order-detail / fill-status reconciliation
10. Supabase execution journal and audit trail
11. Strategy-to-order intent bridge
12. User approval token / confirmation gate
13. Only after Webull eligibility and a separate security review: design a production adapter

Target architecture:

`market data -> buy gate -> sizing -> order intent -> risk guard -> user approval -> broker adapter -> fill reconciliation -> TradeLot -> monitoring -> sell gate -> order intent`

This keeps analysis, approval, execution and recordkeeping as separate layers so future capabilities can be added without giving the research model unrestricted brokerage access.
