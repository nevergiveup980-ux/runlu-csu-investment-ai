import { buildDecisionReviewPacket } from "./review-packet";
import type { BotDecision, BotPortfolioState } from "./csu-bot-v2";
import type { TradeProposal } from "./trade-proposal";

const portfolio: BotPortfolioState = {
  shares: 1,
  cash: 7000,
  buyingPower: 7000,
  currency: "CAD",
  openOrders: [],
};
const decision: BotDecision = {
  action: "BUY",
  quantity: 1,
  role: "SWING",
  targetShares: 2,
  score: 4,
  confidence: "MEDIUM",
  reasons: ["synthetic"],
  risk: {
    approved: true,
    blockers: [],
    warnings: [],
    resultingShares: 2,
    effectiveShares: 1,
    pendingBuyShares: 0,
    pendingSellShares: 0,
    funds: { cash: 7000, buyingPower: 7000, reservedFunds: 0, availableForNewOrders: 7000 },
  },
  execution: "SIMULATION_ONLY",
  liveTradingEnabled: false,
};
const proposal: TradeProposal = {
  proposalId: "22222222-2222-4222-8222-222222222222",
  mode: "HUMAN_REVIEW_REQUIRED",
  symbol: "CSU.TO",
  action: "BUY",
  quantity: 1,
  orderType: "LIMIT",
  limitPriceCAD: 3000,
  estimatedNotionalCAD: 3000,
  expiresAt: "2099-01-01T00:00:00Z",
  approvalState: "PENDING",
  brokerSubmitted: false,
  reasons: ["synthetic"],
};

const packet = buildDecisionReviewPacket(proposal, decision, portfolio);
if (!packet.simulationOnly || packet.brokerSubmitted) throw new Error("review packet execution flags are unsafe");
if (packet.currentShares !== 1 || packet.targetShares !== 2) throw new Error("review packet share counts are wrong");
if ((packet as any).accountId || (packet as any).cash || (packet as any).buyingPower) throw new Error("review packet leaked private account fields");

let rejected = false;
try {
  buildDecisionReviewPacket({ ...proposal, action: "SELL" }, decision, portfolio);
} catch {
  rejected = true;
}
if (!rejected) throw new Error("decision/proposal mismatch was not rejected");

console.log("review packet safety checks passed");
