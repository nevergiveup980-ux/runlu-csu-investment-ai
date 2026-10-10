export type BotAction = "BUY" | "SELL" | "HOLD";
export type ShareRole = "CORE" | "SWING" | "RESERVE" | "NONE";

export type BotMarketSnapshot = {
  price: number;
  rsi14: number | null;
  macd: number | null;
  macdSignal: number | null;
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  support20: number | null;
  resistance20: number | null;
};

export type OpenOrder = {
  id?: string;
  symbol: string;
  side: "BUY" | "SELL" | "UNKNOWN";
  quantity: number;
  limitPrice?: number | null;
  status: string;
};

export type BotPortfolioState = {
  shares: number;
  cash?: number | null;
  buyingPower?: number | null;
  averageCost?: number | null;
  currency?: string | null;
  openOrders?: OpenOrder[];
  historyCount?: number | null;
};

export type FundsState = {
  cash: number | null;
  buyingPower: number | null;
  reservedFunds: number | null;
  availableForNewOrders: number | null;
};

export type RiskResult = {
  approved: boolean;
  blockers: string[];
  warnings: string[];
  resultingShares: number;
  effectiveShares: number;
  pendingBuyShares: number;
  pendingSellShares: number;
  funds: FundsState;
};

export type BotDecision = {
  action: BotAction;
  quantity: 0 | 1;
  role: ShareRole;
  targetShares: number;
  score: number;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  reasons: string[];
  risk: RiskResult;
  execution: "SIMULATION_ONLY";
  liveTradingEnabled: false;
};

export const CSU_BOT_V2 = Object.freeze({
  product: "RUNLU CSU Bot V2",
  symbol: "CSU.TO",
  strategy: "ADAPTIVE_SWING",
  maxShares: 3,
  coreShares: 1,
  swingShares: 1,
  reserveShares: 1,
  maxOrderShares: 1,
  minimumCashBuffer: 1000,
  allowShorting: false,
  allowMargin: false,
  allowOptions: false,
  liveTradingEnabled: false,
  killSwitch: "ARMED" as const,
});

const isCsu = (symbol: string) => {
  const s = String(symbol || "").toUpperCase().replace(/\s/g, "");
  return s === "CSU" || s === "CSU.TO" || s === "CSU:TSX";
};

const isOpen = (status: string) => !["FILLED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED"].includes(String(status || "").toUpperCase());

export function pendingCsuOrders(state: BotPortfolioState) {
  const orders = (state.openOrders || []).filter((o) => isCsu(o.symbol) && isOpen(o.status));
  const buys = orders.filter((o) => o.side === "BUY");
  const sells = orders.filter((o) => o.side === "SELL");
  const pendingBuyShares = buys.reduce((n, o) => n + Math.max(0, Number(o.quantity) || 0), 0);
  const pendingSellShares = sells.reduce((n, o) => n + Math.max(0, Number(o.quantity) || 0), 0);
  const reservedByOrders = buys.reduce((n, o) => n + Math.max(0, Number(o.quantity) || 0) * Math.max(0, Number(o.limitPrice) || 0), 0);
  return { orders, buys, sells, pendingBuyShares, pendingSellShares, reservedByOrders };
}

export function fundsState(state: BotPortfolioState): FundsState {
  const cash = state.cash != null && Number.isFinite(state.cash) ? state.cash : null;
  const buyingPower = state.buyingPower != null && Number.isFinite(state.buyingPower) ? state.buyingPower : null;
  const reservedFunds = cash != null && buyingPower != null ? Math.max(0, cash - buyingPower) : null;
  return {
    cash,
    buyingPower,
    reservedFunds,
    availableForNewOrders: buyingPower,
  };
}

function scoreMarket(m: BotMarketSnapshot): { score: number; reasons: string[] } {
  let score = 0;
  const reasons: string[] = [];
  if (m.rsi14 != null) {
    if (m.rsi14 < 35) { score += 2; reasons.push("RSI is in a strong oversold zone"); }
    else if (m.rsi14 < 45) { score += 1; reasons.push("RSI is below neutral and may offer a better entry"); }
    else if (m.rsi14 > 72) { score -= 2; reasons.push("RSI is stretched and favors patience or trimming"); }
  }
  if (m.support20 != null) {
    if (m.price <= m.support20 * 1.03) { score += 2; reasons.push("Price is close to 20-day support"); }
    else if (m.price <= m.support20 * 1.07) { score += 1; reasons.push("Price is within the broader support zone"); }
  }
  if (m.resistance20 != null && m.price >= m.resistance20 * 0.99) { score -= 1; reasons.push("Price is close to 20-day resistance"); }
  if (m.macd != null && m.macdSignal != null) {
    m.macd > m.macdSignal ? (score += 1, reasons.push("MACD is above signal")) : (score -= 1, reasons.push("MACD is below signal"));
  }
  if (m.sma20 != null) {
    m.price > m.sma20 ? (score += 1, reasons.push("Price is above SMA20")) : (score -= 1, reasons.push("Price is below SMA20"));
  }
  if (m.sma20 != null && m.sma50 != null) {
    m.sma20 > m.sma50 ? (score += 1, reasons.push("Short-term trend remains constructive")) : (score -= 1, reasons.push("Short-term trend remains weak"));
  }
  if (m.sma200 != null) {
    m.price > m.sma200 ? (score += 1, reasons.push("Price remains above the long-term trend line")) : (score -= 1, reasons.push("Price is below the long-term trend line"));
  }
  return { score, reasons };
}

function riskCheck(action: BotAction, quantity: 0 | 1, state: BotPortfolioState, price: number): RiskResult {
  const blockers: string[] = [];
  const warnings: string[] = [];
  const currentShares = Number.isFinite(state.shares) ? Math.trunc(state.shares) : -1;
  const pending = pendingCsuOrders(state);
  const funds = fundsState(state);
  const effectiveShares = currentShares + pending.pendingBuyShares - pending.pendingSellShares;
  const resultingShares = action === "BUY" ? effectiveShares + quantity : action === "SELL" ? effectiveShares - quantity : effectiveShares;

  if (currentShares < 0 || currentShares > CSU_BOT_V2.maxShares) blockers.push("Current share count is outside the 0-3 authorization range");
  if (quantity > CSU_BOT_V2.maxOrderShares) blockers.push("A single simulated order may not exceed one share");
  if (effectiveShares < 0) blockers.push("Pending sell orders would imply a short position");
  if (effectiveShares > CSU_BOT_V2.maxShares) blockers.push("Current shares plus pending buys exceed the three-share authorization");
  if (resultingShares < 0) blockers.push("Short selling is disabled");
  if (resultingShares > CSU_BOT_V2.maxShares) blockers.push("Three-share hard cap would be exceeded");

  if (action === "BUY" && pending.pendingBuyShares > 0) blockers.push("An open CSU BUY already reserves a share slot; do not stack another simulated buy");
  if (action === "SELL" && pending.pendingSellShares > 0) blockers.push("An open CSU SELL already exists; do not stack another simulated sell");

  if (funds.buyingPower != null && funds.cash != null && funds.buyingPower < funds.cash) {
    warnings.push(`Broker buying power is C$${(funds.cash - funds.buyingPower).toFixed(2)} below cash; funds are reserved or otherwise unavailable`);
  }
  if (action === "BUY" && funds.availableForNewOrders != null) {
    const after = funds.availableForNewOrders - price * quantity;
    if (after < 0) blockers.push("Buying power is below the estimated purchase cost");
    else if (after < CSU_BOT_V2.minimumCashBuffer) blockers.push(`Simulated buy would leave less than the C$${CSU_BOT_V2.minimumCashBuffer} liquidity buffer`);
  }

  return { approved: blockers.length === 0, blockers, warnings, resultingShares, effectiveShares, pendingBuyShares: pending.pendingBuyShares, pendingSellShares: pending.pendingSellShares, funds };
}

function confidence(score: number): "LOW" | "MEDIUM" | "HIGH" {
  const n = Math.abs(score);
  if (n >= 5) return "HIGH";
  if (n >= 3) return "MEDIUM";
  return "LOW";
}

export function buildBotDecision(m: BotMarketSnapshot, state: BotPortfolioState): BotDecision {
  const { score, reasons } = scoreMarket(m);
  const pending = pendingCsuOrders(state);
  const effectiveShares = Math.trunc(state.shares) + pending.pendingBuyShares - pending.pendingSellShares;
  const funds = fundsState(state);

  if (state.historyCount != null) reasons.push(`Broker history available: ${state.historyCount} transactions`);
  if (pending.orders.length) {
    reasons.push(`Detected ${pending.orders.length} open CSU order(s): ${pending.pendingBuyShares} BUY share(s), ${pending.pendingSellShares} SELL share(s)`);
  }
  if (funds.reservedFunds != null && funds.reservedFunds > 0) {
    reasons.push(`C$${funds.reservedFunds.toFixed(2)} is not currently available as buying power`);
  }

  let action: BotAction = "HOLD";
  let quantity: 0 | 1 = 0;
  let role: ShareRole = "NONE";

  const nearSupport = m.support20 != null && m.price <= m.support20 * 1.04;
  const nearResistance = m.resistance20 != null && m.price >= m.resistance20 * 0.99;
  const reserveQuality = score >= 5 && nearSupport && (m.rsi14 == null || m.rsi14 <= 38);

  if (pending.orders.length) {
    reasons.push("Open CSU order detected; robot freezes overlapping action and observes the existing order");
  } else if (effectiveShares === 0 && score >= 3) {
    action = "BUY"; quantity = 1; role = "CORE"; reasons.push("Core entry threshold is satisfied");
  } else if (effectiveShares === 1 && score >= 4) {
    action = "BUY"; quantity = 1; role = "SWING"; reasons.push("Swing-share entry threshold is satisfied");
  } else if (effectiveShares === 2 && reserveQuality) {
    action = "BUY"; quantity = 1; role = "RESERVE"; reasons.push("Reserve share unlocked only by a higher-quality setup");
  } else if (effectiveShares >= 2 && nearResistance && (m.rsi14 ?? 0) >= 70) {
    action = "SELL"; quantity = 1; role = effectiveShares === 3 ? "RESERVE" : "SWING"; reasons.push("Trim one tactical share into an extended resistance setup");
  } else if (effectiveShares >= 2 && score <= -3) {
    action = "SELL"; quantity = 1; role = effectiveShares === 3 ? "RESERVE" : "SWING"; reasons.push("Tactical risk reduction threshold is triggered");
  } else if (effectiveShares === 1 && score <= -6) {
    action = "SELL"; quantity = 1; role = "CORE"; reasons.push("Core exit is allowed only under severe multi-signal deterioration");
  } else {
    reasons.push("No high-quality action threshold is met; cash is a valid position");
  }

  const risk = riskCheck(action, quantity, state, m.price);
  if (!risk.approved) {
    reasons.push(...risk.blockers.map((x) => `Risk engine blocked action: ${x}`));
    action = "HOLD"; quantity = 0; role = "NONE";
  }
  reasons.push(...risk.warnings);

  return {
    action,
    quantity,
    role,
    targetShares: action === "HOLD" ? effectiveShares : risk.resultingShares,
    score,
    confidence: confidence(score),
    reasons,
    risk,
    execution: "SIMULATION_ONLY",
    liveTradingEnabled: false,
  };
}

export function botStatus() {
  return {
    ...CSU_BOT_V2,
    allocation: {
      core: "1 share · patient core position",
      swing: "1 share · normal swing trading",
      reserve: "1 share · higher-threshold tactical reserve",
    },
    style: "Swing first; intraday only as a later tactical extension",
    accountAware: true,
    openOrderAware: true,
    buyingPowerAware: true,
    simulationOnly: true,
    noTradeIsValid: true,
    brokerExecution: "READ_ONLY_NO_WRITES",
  };
}
