# RUNLU Webull Bot V2 — Trading Readiness

A sandbox-first Webull OpenAPI integration that prepares RUNLU Investment AI for a future user-confirmed US-stock execution workflow.

## What changed in V2

V2 adds a real order-execution **scaffold**, but it remains hard-locked to Webull Sandbox. It can now:

- connect to the Webull Sandbox account;
- build a US equity LIMIT order using Webull's official `order_v3.place_order` SDK method;
- validate every order through a separate risk guard before any broker call;
- preview an order without touching Webull;
- submit a sandbox order only after two independent arming steps;
- run automated guard tests in GitHub Actions.

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

This performs validation only and makes **no broker call**:

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
2. Independent order risk guard — built
3. Dry-run / order preview — built
4. Guarded sandbox order placement — built
5. Balance + positions pre-trade checks
6. Order-detail / fill-status reconciliation
7. Supabase execution journal and audit trail
8. Strategy-to-order intent bridge
9. User approval token / confirmation gate
10. Only after Webull eligibility and a separate security review: design a production adapter

The target architecture is:

`market data -> AI/strategy -> order intent -> risk guard -> user approval -> broker adapter -> order status -> audit log`

This keeps analysis, approval, execution and recordkeeping as separate layers so future capabilities can be added without giving the research model unrestricted brokerage access.
