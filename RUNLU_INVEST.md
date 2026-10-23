# RUNLU INVEST V0.1

RUNLU INVEST is the public, read-only product branch extracted from the private CSU research robot.

## Product thesis

**The investment companion that remembers.**

The product is not a brokerage and does not place, modify, or cancel orders. Its first differentiator is Investment Memory: each holding can accumulate a timeline of decisions, reasons, notes, and outcomes.

## V0.1 domain model

Portfolio → Holding → Investment Memory → Review

A holding is no longer hard-coded to CSU. CSU becomes one valid holding instance among many.

## Safety boundary

- READ-ONLY is the public-product baseline.
- No order placement, modification, cancellation, or execution endpoints.
- Private CSU strategy preferences must not be copied into the public product.
- Market-data access and future brokerage-data access remain separate from any execution capability.

## Migration

The existing indicator engine can be reused. The next engineering step is to parameterize symbol/exchange in the market-data layer and replace the CSU-specific dashboard identity with portfolio/holding selection.
