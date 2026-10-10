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

export type BotPortfolioState = {
  shares: number;
  cash?: number | null;
  averageCost?: number | null;
};

export type RiskResult = {
  approved: boolean;
  blockers: string[];
  resultingShares: number;
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
  execution: "PREVIEW_ONLY";
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
  allowShorting: false,
  allowMargin: false,
  allowOptions: false,
  liveTradingEnabled: false,
  killSwitch: "ARMED" as const,
});

function scoreMarket(m: BotMarketSnapshot): { score: number; reasons: string[] } {
  let score = 0;
  const reasons: string[] = [];

  if (m.rsi14 != null) {
    if (m.rsi14 < 35) {
      score += 2;
      reasons.push("RSI is in a strong oversold zone");
    } else if (m.rsi14 < 45) {
      score += 1;
      reasons.push("RSI is below neutral and may offer a better entry");
    } else if (m.rsi14 > 72) {
      score -= 2;
      reasons.push("RSI is stretched and favors patience or trimming");
    }
  }

  if (m.support20 != null) {
    if (m.price <= m.support20 * 1.03) {
      score += 2;
      reasons.push("Price is close to 20-day support");
    } else if (m.price <= m.support20 * 1.07) {
      score += 1;
      reasons.push("Price is within the broader support zone");
    }
  }

  if (m.resistance20 != null && m.price >= m.resistance20 * 0.99) {
    score -= 1;
    reasons.push("Price is close to 20-day resistance");
  }

  if (m.macd != null && m.macdSignal != null) {
    if (m.macd > m.macdSignal) {
      score += 1;
      reasons.push("MACD is above signal");
    } else {
      score -= 1;
      reasons.push("MACD is below signal");
    }
  }

  if (m.sma20 != null) {
    if (m.price > m.sma20) {
      score += 1;
      reasons.push("Price is above SMA20");
    } else {
      score -= 1;
      reasons.push("Price is below SMA20");
    }
  }

  if (m.sma20 != null && m.sma50 != null) {
    if (m.sma20 > m.sma50) {
      score += 1;
      reasons.push("Short-term trend remains constructive");
    } else {
      score -= 1;
      reasons.push("Short-term trend remains weak");
    }
  }

  if (m.sma200 != null) {
    if (m.price > m.sma200) {
      score += 1;
      reasons.push("Price remains above the long-term trend line");
    } else {
      score -= 1;
      reasons.push("Price is below the long-term trend line");
    }
  }

  return { score, reasons };
}

function riskCheck(action: BotAction, quantity: 0 | 1, state: BotPortfolioState, price: number): RiskResult {
  const blockers: string[] = [];
  const currentShares = Number.isFinite(state.shares) ? Math.trunc(state.shares) : -1;
  const resultingShares = action === "BUY"
    ? currentShares + quantity
    : action === "SELL"
      ? currentShares - quantity
      : currentShares;

  if (currentShares < 0 || currentShares > CSU_BOT_V2.maxShares) {
    blockers.push("Current share count is outside the 0-3 authorization range");
  }
  if (quantity > CSU_BOT_V2.maxOrderShares) {
    blockers.push("A single order may not exceed one share");
  }
  if (resultingShares < 0) blockers.push("Short selling is disabled");
  if (resultingShares > CSU_BOT_V2.maxShares) blockers.push("Three-share hard cap would be exceeded");
  if (action === "BUY" && state.cash != null && Number.isFinite(state.cash) && state.cash < price * quantity) {
    blockers.push("Available cash is below the estimated purchase cost");
  }

  return { approved: blockers.length === 0, blockers, resultingShares };
}

function confidence(score: number): "LOW" | "MEDIUM" | "HIGH" {
  const n = Math.abs(score);
  if (n >= 5) return "HIGH";
  if (n >= 3) return "MEDIUM";
  return "LOW";
}

export function buildBotDecision(m: BotMarketSnapshot, state: BotPortfolioState): BotDecision {
  const { score, reasons } = scoreMarket(m);
  const shares = Math.trunc(state.shares);

  let action: BotAction = "HOLD";
  let quantity: 0 | 1 = 0;
  let role: ShareRole = "NONE";

  const nearSupport = m.support20 != null && m.price <= m.support20 * 1.04;
  const nearResistance = m.resistance20 != null && m.price >= m.resistance20 * 0.99;
  const reserveQuality = score >= 5 && nearSupport && (m.rsi14 == null || m.rsi14 <= 38);

  if (shares === 0 && score >= 3) {
    action = "BUY";
    quantity = 1;
    role = "CORE";
    reasons.push("Core entry threshold is satisfied");
  } else if (shares === 1 && score >= 4) {
    action = "BUY";
    quantity = 1;
    role = "SWING";
    reasons.push("Swing-share entry threshold is satisfied");
  } else if (shares === 2 && reserveQuality) {
    action = "BUY";
    quantity = 1;
    role = "RESERVE";
    reasons.push("Reserve share unlocked only by a higher-quality setup");
  } else if (shares >= 2 && nearResistance && (m.rsi14 ?? 0) >= 70) {
    action = "SELL";
    quantity = 1;
    role = shares === 3 ? "RESERVE" : "SWING";
    reasons.push("Trim one tactical share into an extended resistance setup");
  } else if (shares >= 2 && score <= -3) {
    action = "SELL";
    quantity = 1;
    role = shares === 3 ? "RESERVE" : "SWING";
    reasons.push("Tactical risk reduction threshold is triggered");
  } else if (shares === 1 && score <= -6) {
    action = "SELL";
    quantity = 1;
    role = "CORE";
    reasons.push("Core exit is allowed only under severe multi-signal deterioration");
  } else {
    reasons.push("No high-quality action threshold is met; cash is a valid position");
  }

  const risk = riskCheck(action, quantity, state, m.price);
  if (!risk.approved) {
    reasons.push(...risk.blockers.map((x) => `Risk engine blocked action: ${x}`));
    action = "HOLD";
    quantity = 0;
    role = "NONE";
  }

  return {
    action,
    quantity,
    role,
    targetShares: action === "HOLD" ? shares : risk.resultingShares,
    score,
    confidence: confidence(score),
    reasons,
    risk,
    execution: "PREVIEW_ONLY",
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
    noTradeIsValid: true,
    brokerExecution: "DISABLED_UNTIL_SEPARATELY_REVIEWED",
  };
}
