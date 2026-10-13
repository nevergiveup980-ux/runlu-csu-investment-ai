# CSU Bot V2 — Read-Only Account-Aware Experimental Trader

CSU Bot V2 is a **three-share Adaptive Swing research system**. It can use a real read-only broker snapshot, but it cannot place, modify, or cancel an order.

## Three-share architecture

- **Core** — 1 patient base share.
- **Swing** — 1 normal tactical share.
- **Reserve** — 1 higher-threshold share.
- Hard maximum exposure: **3 shares**.
- Maximum simulated position change per decision: **1 share**.
- Cash / NO TRADE is a valid position.

## Real-data inputs

The normalized broker snapshot supports:

- real cash
- real buying power
- current CSU quantity and average cost
- open CSU orders
- transaction-history count

The strategy uses **buying power**, not headline cash, for a new simulated purchase. The difference between cash and buying power is treated as reserved/unavailable money and is shown by the risk engine.

### Current verified connection checkpoint

At the time this milestone was created, the verified read-only Webull Canada → SnapTrade → Dashboard snapshot was:

- Cash: **C$9,895.53**
- Buying power: **C$7,045.53**
- Reserved / unavailable difference: **C$2,850.00**
- History records available: **33**
- The C$2,850 difference was confirmed to correspond to an unfilled CSU buy limit order.

These values are a checkpoint for validation only. Runtime decisions should use the latest broker snapshot, not these hard-coded figures.

## Open-order rules

An open CSU order changes the bot's **effective exposure** before any new recommendation is considered.

`effectiveShares = heldShares + pendingBuyShares - pendingSellShares`

If an open CSU BUY or SELL is detected, CSU Bot V2 freezes overlapping action instead of stacking a second order. The existing real order remains untouched.

## Funds rules

- New simulated buys are tested against **buying power**.
- The bot preserves a minimum **C$1,000 liquidity buffer** after a simulated buy.
- Cash minus buying power is reported as reserved/unavailable.
- No margin, leverage, shorting, or options.

## Paper simulation

`GET /api/bot/simulate` runs the decision through an isolated paper ledger.

The ledger records a hypothetical fill and hypothetical cash/share changes only. It has no broker-write capability and every paper fill is marked `realOrderPlaced: false`.

## API

- `GET /api/bot/status`
- `GET /api/bot/preview?shares=0&cash=9895.53&buyingPower=7045.53&historyCount=33`
- `GET /api/bot/simulate?...same account fields...`
- `openOrders` may be supplied as URL-encoded JSON until the live dashboard adapter passes the normalized read-only snapshot directly.

## Safety boundary

- Live trading: **OFF**
- Broker mode: **READ_ONLY**
- Place order: **blocked**
- Modify order: **blocked**
- Cancel order: **blocked**
- Kill switch: **ARMED**

The next integration step is to feed the already-working SnapTrade/Webull dashboard snapshot into the normalized `BrokerAccountSnapshot` adapter so the user no longer needs to type account fields into a preview URL.
