import type { BrokerAccountSnapshot } from "./broker-bridge";
import type { TradeProposal } from "./trade-proposal";

export type HumanApproval = {
  proposalId: string;
  approved: boolean;
  approvedAt: string;
};

export type LiveQuote = {
  symbol: "CSU.TO";
  priceCAD: number;
  asOf: string;
};

export type ExecutionPreflightInput = {
  proposal: TradeProposal;
  approval: HumanApproval;
  snapshot: BrokerAccountSnapshot;
  quote: LiveQuote;
  accountId: string;
  universalSymbolId: string;
  now: string;
  killSwitchArmed: boolean;
  maxSnapshotAgeSeconds: number;
  maxQuoteAgeSeconds: number;
  maxLimitDriftPct: number;
};

export type SnapTradeEquityLimitOrderPayload = {
  account_id: string;
  action: "BUY" | "SELL";
  universal_symbol_id: string;
  symbol: null;
  order_type: "Limit";
  time_in_force: "Day";
  trading_session: "REGULAR";
  price: number;
  stop: null;
  units: 1;
  notional_value: null;
  client_order_id: string;
};

const openStatus = (status: string) =>
  !["FILLED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED"].includes(String(status || "").toUpperCase());

export function executionPreflight(input: ExecutionPreflightInput) {
  const blockers: string[] = [];
  const now = Date.parse(input.now);
  const expiry = Date.parse(input.proposal.expiresAt);
  const approvedAt = Date.parse(input.approval.approvedAt);
  const snapshotAt = Date.parse(input.snapshot.fetchedAt);
  const quoteAt = Date.parse(input.quote.asOf);

  if (!input.killSwitchArmed) blockers.push("Kill switch is not armed for execution");
  if (!input.approval.approved) blockers.push("Human approval is absent");
  if (input.approval.proposalId !== input.proposal.proposalId) blockers.push("Approval does not match proposal");
  if (![now, expiry, approvedAt, snapshotAt, quoteAt].every(Number.isFinite)) blockers.push("Timestamp validation failed");
  if (Number.isFinite(now) && Number.isFinite(expiry) && now >= expiry) blockers.push("Proposal expired");
  if (Number.isFinite(approvedAt) && Number.isFinite(expiry) && approvedAt >= expiry) blockers.push("Approval occurred after expiry");
  if (input.proposal.symbol !== "CSU.TO" || input.quote.symbol !== "CSU.TO") blockers.push("Only CSU.TO is authorized");
  if (input.proposal.quantity !== 1 || input.proposal.orderType !== "LIMIT") blockers.push("Only one-share limit orders are authorized");
  if (!input.accountId) blockers.push("Private brokerage account id is required");
  if (!input.universalSymbolId) blockers.push("Verified SnapTrade universal symbol id is required");
  if (input.snapshot.accountId && input.snapshot.accountId !== input.accountId) blockers.push("Snapshot account does not match execution account");
  if (input.snapshot.currency !== "CAD") blockers.push("CAD account required");
  if (!Number.isFinite(input.quote.priceCAD) || input.quote.priceCAD <= 0) blockers.push("Live quote is invalid");
  if (input.maxSnapshotAgeSeconds <= 0 || input.maxQuoteAgeSeconds <= 0 || input.maxLimitDriftPct < 0) blockers.push("Preflight thresholds are invalid");

  if (Number.isFinite(now) && Number.isFinite(snapshotAt) && (now - snapshotAt) / 1000 > input.maxSnapshotAgeSeconds) blockers.push("Account snapshot is stale");
  if (Number.isFinite(now) && Number.isFinite(quoteAt) && (now - quoteAt) / 1000 > input.maxQuoteAgeSeconds) blockers.push("Market quote is stale");
  if (Number.isFinite(now) && Number.isFinite(snapshotAt) && snapshotAt > now + 5000) blockers.push("Account snapshot is unexpectedly in the future");
  if (Number.isFinite(now) && Number.isFinite(quoteAt) && quoteAt > now + 5000) blockers.push("Market quote is unexpectedly in the future");

  const openCsuOrders = (input.snapshot.openOrders || []).filter(o =>
    ["CSU", "CSU.TO", "CSU:TSX"].includes(String(o.symbol || "").toUpperCase()) && openStatus(o.status)
  );
  if (openCsuOrders.length) blockers.push("Existing open CSU order must be reconciled first");

  const held = Math.trunc((input.snapshot.positions || []).find(p =>
    ["CSU", "CSU.TO", "CSU:TSX"].includes(String(p.symbol || "").toUpperCase())
  )?.quantity || 0);
  const resultingShares = input.proposal.action === "BUY" ? held + 1 : held - 1;
  if (resultingShares < 0) blockers.push("Short selling is disabled");
  if (resultingShares > 3) blockers.push("Three-share hard cap would be exceeded");

  if (input.proposal.action === "BUY") {
    const buyingPower = input.snapshot.buyingPower;
    if (buyingPower == null || !Number.isFinite(buyingPower)) blockers.push("Buying power is unavailable");
    else if (buyingPower - input.proposal.limitPriceCAD < 1000) blockers.push("Configured cash buffer would be breached");
  }

  if (Number.isFinite(input.quote.priceCAD) && input.quote.priceCAD > 0) {
    const driftPct = Math.abs(input.proposal.limitPriceCAD - input.quote.priceCAD) / input.quote.priceCAD * 100;
    if (driftPct > input.maxLimitDriftPct) blockers.push("Limit price drift exceeds configured threshold");
  }

  const payload: SnapTradeEquityLimitOrderPayload | null = blockers.length ? null : {
    account_id: input.accountId,
    action: input.proposal.action,
    universal_symbol_id: input.universalSymbolId,
    symbol: null,
    order_type: "Limit",
    time_in_force: "Day",
    trading_session: "REGULAR",
    price: input.proposal.limitPriceCAD,
    stop: null,
    units: 1,
    notional_value: null,
    client_order_id: input.proposal.proposalId,
  };

  return {
    ready: blockers.length === 0,
    blockers,
    resultingShares,
    payload,
    submitted: false,
  };
}
