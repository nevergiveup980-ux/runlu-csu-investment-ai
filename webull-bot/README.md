# RUNLU Webull Bot V1.0

A sandbox-first Webull OpenAPI integration for US stock research and account monitoring.

## Safety mode

V1.0 is **SANDBOX / READ-ONLY by default**. It is designed to verify authentication, account access, balances and positions before any order workflow is enabled.

No credentials belong in this repository. Use environment variables or GitHub Actions Secrets only.

## Required secrets

- `WEBULL_APP_KEY`
- `WEBULL_APP_SECRET`

Optional for later phases:
- `WEBULL_ACCOUNT_ID`
- `WEBULL_ACCESS_TOKEN`

## Environment

Sandbox host: `api.sandbox.webull.com`
Production host: `api.webull.com`

V1.0 hard-locks the client to sandbox unless the code is deliberately changed in a later reviewed version.

## First test

```bash
pip install -r webull-bot/requirements.txt
python webull-bot/src/sandbox_check.py
```

Expected result: a sanitized account list / connection status. The script does not place orders.

## Planned phases

1. Sandbox connection + account list
2. Balance + positions read-only dashboard
3. Market-data adapter
4. BUY / HOLD / SELL research layer
5. Sandbox order preview
6. Paper execution log
7. Optional user-confirmed live execution layer

Real-money autonomous trading is intentionally outside V1.0.
