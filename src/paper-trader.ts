import type { BotAction, BotDecision, BotPortfolioState, ShareRole } from "./csu-bot-v2";

export type PaperFill = {
  id: string;
  symbol: "CSU.TO";
  action: Exclude<BotAction, "HOLD">;
  quantity: 1;
  role: Exclude<ShareRole, "NONE">;
  simulatedPrice: number;
  createdAt: string;
  source: "CSU_BOT_V2";
  realOrderPlaced: false;
};

export type PaperLedger = {
  startingShares: number;
  startingCash: number | null;
  simulatedShares: number;
  simulatedCash: number | null;
  fills: PaperFill[];
};

export function createPaperLedger(state: BotPortfolioState): PaperLedger {
  return {
    startingShares: state.shares,
    startingCash: state.buyingPower ?? state.cash ?? null,
    simulatedShares: state.shares,
    simulatedCash: state.buyingPower ?? state.cash ?? null,
    fills: [],
  };
}

export function simulateDecision(ledger: PaperLedger, decision: BotDecision, price: number, now = new Date().toISOString()): PaperLedger {
  if (decision.action === "HOLD" || decision.quantity === 0 || decision.role === "NONE") return ledger;

  const next: PaperLedger = { ...ledger, fills: ledger.fills.slice() };
  if (decision.action === "BUY") {
    if (next.simulatedShares >= 3) return next;
    if (next.simulatedCash != null && next.simulatedCash < price) return next;
    next.simulatedShares += 1;
    if (next.simulatedCash != null) next.simulatedCash -= price;
  } else {
    if (next.simulatedShares <= 0) return next;
    next.simulatedShares -= 1;
    if (next.simulatedCash != null) next.simulatedCash += price;
  }

  next.fills.push({
    id: `paper-${now}-${next.fills.length + 1}`,
    symbol: "CSU.TO",
    action: decision.action,
    quantity: 1,
    role: decision.role,
    simulatedPrice: price,
    createdAt: now,
    source: "CSU_BOT_V2",
    realOrderPlaced: false,
  });
  return next;
}
