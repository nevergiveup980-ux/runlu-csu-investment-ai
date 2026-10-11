/**
 * A reviewable order proposal, NOT a brokerage order.
 * This module deliberately has no network access and cannot place trades.
 */
import type { BotDecision, BotPortfolioState } from "./csu-bot-v2";

export type TradeProposal = {
  proposalId: string;
  mode: "HUMAN_REVIEW_REQUIRED";
  symbol: "CSU.TO";
  action: "BUY" | "SELL";
  quantity: 1;
  orderType: "LIMIT";
  limitPriceCAD: number;
  estimatedNotionalCAD: number;
  expiresAt: string;
  approvalState: "PENDING";
  brokerSubmitted: false;
  reasons: string[];
};

export function createTradeProposal(
  proposalId: string,
  decision: BotDecision,
  portfolio: BotPortfolioState,
  limitPriceCAD: number,
  expiresAt: string,
): TradeProposal | null {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(proposalId)) return null;
  if (decision.action === "HOLD" || decision.quantity !== 1 || !decision.risk.approved) return null;
  if (portfolio.currency !== "CAD") return null;
  if (!Number.isFinite(limitPriceCAD) || limitPriceCAD <= 0) return null;
  if (!Number.isFinite(Date.parse(expiresAt)) || Date.parse(expiresAt) <= Date.now()) return null;
  if (decision.action === "BUY") {
    if (portfolio.buyingPower == null || !Number.isFinite(portfolio.buyingPower)) return null;
    if (portfolio.buyingPower - limitPriceCAD < 1000) return null;
  }
  if ((portfolio.openOrders || []).some(o => ["CSU", "CSU.TO", "CSU:TSX"].includes(o.symbol.toUpperCase()))) return null;
  return {
    proposalId,
    mode: "HUMAN_REVIEW_REQUIRED",
    symbol: "CSU.TO",
    action: decision.action,
    quantity: 1,
    orderType: "LIMIT",
    limitPriceCAD,
    estimatedNotionalCAD: limitPriceCAD,
    expiresAt,
    approvalState: "PENDING",
    brokerSubmitted: false,
    reasons: decision.reasons,
  };
}
