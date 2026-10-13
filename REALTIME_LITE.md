# CSU Realtime Lite V1

Realtime Lite gives CSU Bot a **1-5 minute observation loop** without enabling
brokerage writes.

## What it does

1. The existing read-only local bridge caches its latest **sanitized** broker
   snapshot under the gitignored `.csu-private/` directory.
2. `bridge/realtime_lite.py` wakes every 60-300 seconds (default: 180).
3. It sends the recent sanitized snapshot to the protected
   `/api/bot/realtime-proposal` endpoint.
4. The Worker requests Twelve Data intraday bars at either `1min` or `5min`.
5. CSU Bot recalculates indicators, strategy, and risk using the fresh market
   price.
6. HOLD produces no approval card.
7. A new BUY/SELL signal episode sends only the sanitized `reviewPacket` to
   `http://127.0.0.1:8775`.
8. Repeated bars and repeated signal episodes are suppressed so the operator is
   not spammed. A persistent signal may be re-notified after the configured
   cooldown.

**No brokerage order is submitted, modified, or cancelled by this loop.**

## Safety behavior

- Polling cadence is hard limited to **60-300 seconds**.
- Cached account snapshots older than **15 minutes** are rejected.
- Snapshot timestamps more than five minutes in the future are rejected.
- The private bot endpoint requires `CSU_SNAPSHOT_TOKEN`.
- Twelve Data credentials remain server-side in the Worker environment.
- The approval panel remains loopback-only.
- The realtime service never receives broker API credentials.
- If the same market bar is returned twice, it is not reprocessed.
- HOLD clears the prior signal episode so a later BUY/SELL transition can notify
  again.
- Live brokerage submission remains disabled.

## Configuration

```text
CSU_REALTIME_POLL_SECONDS=180       # 60..300; default 3 minutes
CSU_REALTIME_MARKET_INTERVAL=1min   # 1min or 5min
CSU_REALTIME_PROPOSAL_URL=...       # protected Worker endpoint
CSU_SNAPSHOT_TOKEN=...              # private bearer secret; never commit
```

The Worker must also have `TWELVE_DATA_API_KEY` configured privately.

## Local startup order

1. Start the existing read-only SnapTrade bridge.
2. Start `bridge/approval_panel.py`.
3. Refresh the read-only account once so `.csu-private/latest-snapshot.json`
   is current.
4. Start `bridge/realtime_lite.py`.

The default cadence is intentionally three minutes. For RUNLU's swing-first CSU
strategy, this provides frequent observation without pretending to be a
high-frequency trading system.

## Current execution boundary

```text
Twelve Data 1m/5m market bars
        |
Realtime Lite 1-5 minute scheduler
        |
Protected CSU realtime strategy + risk
        |
HOLD ----------------------------> quiet
BUY / SELL
        |
Sanitized reviewPacket
        |
localhost approval panel
        |
APPROVE / REJECT + private audit ledger
        |
BROKER SUBMISSION: DISABLED
```
