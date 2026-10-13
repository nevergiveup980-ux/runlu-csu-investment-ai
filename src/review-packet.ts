/** Sanitized, non-executable packet for the localhost human-review panel. */
import type { BotDecision, BotPortfolioState } from "./csu-bot-v2";
import type { TradeProposal } from "./trade-proposal";

export type DecisionReviewPacket = {
  kind: "CSU_DECISION_REVIEW";
  version: 1;
  proposalId: string;
  symbol: "CSU.TO";
  action: "BUY" | "SELL";
  quantity: 1;
  indicativeLimitCAD: number;
  expiresAt: string;
  role: string;
  currentShares: number;
  targetShares: number;
  score: number;
  confidence: string;
  reasons: string[];
  simulationOnly: true;
  brokerSubmitted: false;
};

export function buildDecisionReviewPacket(
  proposal: TradeProposal,
  decision: BotDecision,
  portfolio: BotPortfolioState,
): DecisionReviewPacket {
  if (proposal.symbol !== "CSU.TO" || proposal.quantity !== 1) {
    throw new Error("Only one-share CSU proposals may enter review");
  }
  if (decision.action !== proposal.action || decision.quantity !== 1) {
    throw new Error("Decision and proposal do not match");
  }
  if (!decision.risk.approved) throw new Error("Risk approval is required");
  const currentShares = Math.trunc(portfolio.shares);
  if (currentShares < 0 || currentShares > 3) throw new Error("Invalid current share count");
  if (decision.targetShares < 0 || decision.targetShares > 3) throw new Error("Invalid target share count");

  return {
    kind: "CSU_DECISION_REVIEW",
    version: 1,
    proposalId: proposal.proposalId,
    symbol: "CSU.TO",
    action: proposal.action,
    quantity: 1,
    indicativeLimitCAD: proposal.limitPriceCAD,
    expiresAt: proposal.expiresAt,
    role: decision.role,
    currentShares,
    targetShares: decision.targetShares,
    score: decision.score,
    confidence: decision.confidence,
    reasons: [...proposal.reasons],
    simulationOnly: true,
    brokerSubmitted: false,
  };
}
