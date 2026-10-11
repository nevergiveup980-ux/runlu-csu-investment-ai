# RUNLU Scout V1

RUNLU Scout V1 adds **research discovery and screening** beside the CSU-first
trading assistant. CSU remains the primary strategy and execution candidate.

Scout V1 does **not** trade. It cannot create brokerage orders and it cannot make
another stock execution-eligible by itself.

## Mission

Scout answers only:

> Which stocks in a small curated TSX universe deserve our next round of
> research?

It does not answer:

> Which stock should be bought automatically?

## V1 screening flow

```text
Curated TSX universe (1-8 symbols per scan)
        |
Daily technical history
        |
Scout score 0-100
        |
PRIORITY_RESEARCH / RESEARCH / PASS_FOR_NOW
        |
RESEARCH_REQUIRED
        |
joint research by user + assistant
        |
PASS / WATCH / APPROVED_UNIVERSE
        |
still NOT trade eligible
```

The protected endpoint is:

`POST /api/scout/scan`

It requires the existing private bearer token and accepts 1-8 unique symbols in
`TICKER:TSX` format.

## What Scout scores

Scout V1 prefers research setups consistent with RUNLU's current style:

- pullbacks near recent support;
- RSI that is weak/neutral rather than extended;
- price above the long-term trend when possible;
- constructive short-term trend structure;
- MACD improvement;
- meaningful room before recent resistance;
- normal rather than extreme volume.

It also raises explicit risk flags for:

- breaks below recent support;
- very weak RSI / falling-knife risk;
- price below SMA200;
- short-term trend deterioration;
- sharp recent drops;
- chase risk after large rises;
- unusual volume spikes.

These are **research heuristics**, not investment recommendations.

## Mandatory joint research gate

Every new candidate is born as:

`RESEARCH_REQUIRED`

No automatic promotion is allowed.

To record a final outcome, the research record must include:

- research complete;
- assistant research complete;
- explicit user confirmation;
- bull thesis;
- bear case;
- key risks;
- invalidation condition;
- final decision: PASS, WATCH, or APPROVED.

Even `APPROVED_UNIVERSE` means only that the stock may be watched more closely.
Scout V1 keeps:

`tradeEligible = false`

for every non-CSU candidate.

## Private registry

`bridge/scout_registry.py` stores Scout state under:

`.csu-private/scout-registry.json`

This directory is gitignored.

A later scan can update score, reasons, risk flags, and market timestamp, but it
does not erase an existing human research verdict.

`bridge/scout_review_cli.py` can import a scan JSON, list ranked candidates,
and record a completed joint-review decision locally.

## Current limitation

Scout V1 scans a **curated universe**, not the entire TSX automatically. This is
intentional: it lets us validate ranking quality and API cost before adding a
broader market-discovery feed.

CSU continues to use the dedicated strategy, realtime-lite loop, risk engine,
proposal path, and localhost approval flow.


## Scout Hunter V1 — automatic candidate-pool generator

Scout no longer has to wait for us to type every symbol manually.

The protected endpoint `GET /api/scout/universe` requests Twelve Data's TSX
stock catalog and keeps only ordinary Canadian TSX common-stock metadata. It
returns a **research universe only**; catalog membership never grants realtime
or trading permission.

`bridge/scout_hunter.py` then:

1. caches the sanitized TSX research catalog locally for 12 hours;
2. removes CSU from the hunting rotation because CSU remains the primary bot;
3. remembers a private cursor in `.csu-private/scout-hunter-state.json`;
4. selects at most 8 new symbols per cycle;
5. asks `/api/scout/scan` to score that batch;
6. merges results into the private Scout registry;
7. advances the cursor so later cycles explore different stocks;
8. reports only the current top research candidates.

This creates a slow, cost-aware market search instead of hammering every TSX
symbol at once.

A full rotation does **not** imply approval. Every discovered stock still enters
`RESEARCH_REQUIRED` and must pass the user + assistant joint-research gate.

## Authority boundary after Hunter

```text
TSX catalog
   |
Scout Hunter rotation
   |
Scout technical ranking
   |
RESEARCH_REQUIRED
   |
user + assistant research
   |
PASS / WATCH / APPROVED_UNIVERSE
   |
tradeEligible = false
```

CSU remains the only symbol connected to the existing dedicated proposal and
execution-readiness architecture.
