import { createTradeProposal } from "./trade-proposal";
import type { BotDecision, BotPortfolioState } from "./csu-bot-v2";

const risk = {
  approved: true, blockers: [], warnings: [], resultingShares: 2, effectiveShares: 1,
  pendingBuyShares: 0, pendingSellShares: 0,
  funds: { cash: 7000, buyingPower: 7000, reservedFunds: 0, availableForNewOrders: 7000 },
};
const decision: BotDecision = {
  action: "BUY", quantity: 1, role: "SWING", targetShares: 2, score: 4,
  confidence: "MEDIUM", reasons: ["test"], risk,
  execution: "SIMULATION_ONLY", liveTradingEnabled: false,
};
const portfolio: BotPortfolioState = {
  shares: 1, cash: 7000, buyingPower: 7000, currency: "CAD", openOrders: [],
};
const expiry = new Date(Date.now() + 60_000).toISOString();
if (!createTradeProposal(decision, portfolio, 3000, expiry)) throw new Error("valid proposal rejected");
if (createTradeProposal(decision, { ...portfolio, buyingPower: 3500 }, 3000, expiry)) throw new Error("cash buffer bypassed");
if (createTradeProposal(decision, { ...portfolio, openOrders: [{ symbol: "CSU.TO", side: "BUY", quantity: 1, status: "OPEN" }] }, 3000, expiry)) throw new Error("open-order guard bypassed");
if (createTradeProposal({ ...decision, action: "HOLD", quantity: 0 }, portfolio, 3000, expiry)) throw new Error("HOLD generated proposal");
console.log("trade proposal safety checks passed");
