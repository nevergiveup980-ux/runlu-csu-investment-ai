import { executionPreflight } from "./execution-preflight";
import type { TradeProposal } from "./trade-proposal";
import type { BrokerAccountSnapshot } from "./broker-bridge";

const now = new Date();
const nowIso = now.toISOString();
const proposal: TradeProposal = {
  proposalId: "11111111-1111-4111-8111-111111111111",
  mode: "HUMAN_REVIEW_REQUIRED",
  symbol: "CSU.TO",
  action: "BUY",
  quantity: 1,
  orderType: "LIMIT",
  limitPriceCAD: 3000,
  estimatedNotionalCAD: 3000,
  expiresAt: new Date(now.getTime() + 60_000).toISOString(),
  approvalState: "PENDING",
  brokerSubmitted: false,
  reasons: ["synthetic test"],
};
const snapshot: BrokerAccountSnapshot = {
  provider: "SnapTrade",
  accountId: "acct-synthetic",
  currency: "CAD",
  cash: 7000,
  buyingPower: 7000,
  positions: [{ symbol: "CSU.TO", quantity: 1 }],
  openOrders: [],
  transactions: [],
  fetchedAt: nowIso,
};
const base = {
  proposal,
  approval: { proposalId: proposal.proposalId, approved: true, approvedAt: nowIso },
  snapshot,
  quote: { symbol: "CSU.TO" as const, priceCAD: 3005, asOf: nowIso },
  accountId: "acct-synthetic",
  brokerSymbol: "CSU.TO" as const,
  now: nowIso,
  killSwitchArmed: true,
  maxSnapshotAgeSeconds: 120,
  maxQuoteAgeSeconds: 30,
  maxLimitDriftPct: 1,
};
const ok = executionPreflight(base);
if (!ok.ready || !ok.payload || ok.payload.units !== 1 || ok.payload.client_order_id !== proposal.proposalId) throw new Error("valid execution preflight failed");
const duplicate = executionPreflight({
  ...base,
  snapshot: { ...snapshot, openOrders: [{ symbol: "CSU.TO", side: "BUY", quantity: 1, status: "OPEN" }] },
});
if (duplicate.ready) throw new Error("open order bypassed preflight");
const stale = executionPreflight({
  ...base,
  quote: { ...base.quote, asOf: new Date(now.getTime() - 120_000).toISOString() },
});
if (stale.ready) throw new Error("stale quote bypassed preflight");
const cap = executionPreflight({
  ...base,
  snapshot: { ...snapshot, positions: [{ symbol: "CSU.TO", quantity: 3 }] },
});
if (cap.ready) throw new Error("three-share cap bypassed preflight");
console.log("execution preflight checks passed");
