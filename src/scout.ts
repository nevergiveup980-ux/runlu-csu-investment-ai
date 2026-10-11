/** RUNLU Scout V1 — research discovery only, never a trading signal. */

export type ScoutMarketSnapshot = {
  price: number;
  changePct: number | null;
  rsi14: number | null;
  macd: number | null;
  macdSignal: number | null;
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  support20: number | null;
  resistance20: number | null;
  volumeRatio: number | null;
};

export type ScoutStage =
  | "DISCOVERED"
  | "RESEARCH_REQUIRED"
  | "WATCH"
  | "PASS"
  | "APPROVED_UNIVERSE";

export type ScoutCandidate = {
  symbol: string;
  score: number;
  tier: "PRIORITY_RESEARCH" | "RESEARCH" | "PASS_FOR_NOW";
  stage: "RESEARCH_REQUIRED";
  researchRequired: true;
  tradeEligible: false;
  realtimeEligible: false;
  reasons: string[];
  riskFlags: string[];
  snapshot: ScoutMarketSnapshot;
};

const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)));

export function scoreScoutCandidate(symbol: string, m: ScoutMarketSnapshot): ScoutCandidate {
  const reasons: string[] = [];
  const riskFlags: string[] = [];
  let score = 35;

  if (!Number.isFinite(m.price) || m.price <= 0) {
    throw new Error("Scout price must be positive");
  }

  if (m.support20 != null && m.support20 > 0) {
    const distance = (m.price - m.support20) / m.support20;
    if (distance >= 0 && distance <= 0.03) {
      score += 18;
      reasons.push("Price is within 3% of 20-day support");
    } else if (distance > 0.03 && distance <= 0.07) {
      score += 10;
      reasons.push("Price is within the broader support zone");
    } else if (distance < -0.02) {
      score -= 12;
      riskFlags.push("Price has broken materially below recent support");
    }
  }

  if (m.rsi14 != null) {
    if (m.rsi14 >= 30 && m.rsi14 <= 42) {
      score += 15;
      reasons.push("RSI shows a controlled pullback rather than strength chasing");
    } else if (m.rsi14 > 42 && m.rsi14 <= 55) {
      score += 6;
      reasons.push("RSI remains neutral enough for further research");
    } else if (m.rsi14 < 25) {
      score -= 6;
      riskFlags.push("RSI is extremely weak; falling-knife risk requires research");
    } else if (m.rsi14 >= 70) {
      score -= 15;
      riskFlags.push("RSI is elevated; candidate may be too extended");
    }
  }

  if (m.sma200 != null) {
    if (m.price >= m.sma200) {
      score += 12;
      reasons.push("Price remains above the long-term trend line");
    } else {
      score -= 14;
      riskFlags.push("Price is below SMA200; long-term trend needs explanation");
    }
  }

  if (m.sma20 != null && m.sma50 != null) {
    if (m.sma20 >= m.sma50) {
      score += 8;
      reasons.push("Short-term trend structure remains constructive");
    } else {
      score -= 5;
      riskFlags.push("SMA20 is below SMA50");
    }
  }

  if (m.macd != null && m.macdSignal != null) {
    if (m.macd >= m.macdSignal) {
      score += 8;
      reasons.push("MACD is at or above signal");
    } else {
      score -= 3;
      riskFlags.push("MACD momentum remains weak");
    }
  }

  if (m.changePct != null) {
    if (m.changePct <= -1 && m.changePct >= -6) {
      score += 6;
      reasons.push("Recent weakness may offer a researchable pullback");
    } else if (m.changePct < -9) {
      score -= 8;
      riskFlags.push("Sharp recent drop requires news and fundamental review");
    } else if (m.changePct > 8) {
      score -= 6;
      riskFlags.push("Large recent rise increases chase risk");
    }
  }

  if (m.resistance20 != null && m.resistance20 > m.price) {
    const room = (m.resistance20 - m.price) / m.price;
    if (room >= 0.08) {
      score += 8;
      reasons.push("There is meaningful room before recent resistance");
    }
  }

  if (m.volumeRatio != null) {
    if (m.volumeRatio >= 0.6 && m.volumeRatio <= 2.5) {
      score += 4;
      reasons.push("Volume is within a normal researchable range");
    } else if (m.volumeRatio > 4) {
      riskFlags.push("Unusual volume spike requires catalyst/news review");
    }
  }

  score = clamp(score);
  const tier = score >= 72
    ? "PRIORITY_RESEARCH"
    : score >= 55
      ? "RESEARCH"
      : "PASS_FOR_NOW";

  return {
    symbol,
    score,
    tier,
    stage: "RESEARCH_REQUIRED",
    researchRequired: true,
    tradeEligible: false,
    realtimeEligible: false,
    reasons,
    riskFlags,
    snapshot: m,
  };
}

export type JointResearchReview = {
  researchComplete: boolean;
  assistantResearchComplete: boolean;
  userConfirmed: boolean;
  finalDecision: "PASS" | "WATCH" | "APPROVED";
  thesis: string;
  bearCase: string;
  keyRisks: string[];
  invalidation: string;
};

export function applyJointResearchReview(candidate: ScoutCandidate, review: JointResearchReview) {
  if (!review.researchComplete || !review.assistantResearchComplete || !review.userConfirmed) {
    throw new Error("Joint research and explicit user confirmation are required");
  }
  if (!review.thesis.trim() || !review.bearCase.trim() || !review.invalidation.trim()) {
    throw new Error("Thesis, bear case, and invalidation are required");
  }
  if (!review.keyRisks.length) throw new Error("At least one key risk is required");

  const stage: ScoutStage = review.finalDecision === "PASS"
    ? "PASS"
    : review.finalDecision === "WATCH"
      ? "WATCH"
      : "APPROVED_UNIVERSE";

  return {
    ...candidate,
    stage,
    researchRequired: false as const,
    realtimeEligible: stage === "WATCH" || stage === "APPROVED_UNIVERSE",
    tradeEligible: false as const,
    research: {
      thesis: review.thesis,
      bearCase: review.bearCase,
      keyRisks: [...review.keyRisks],
      invalidation: review.invalidation,
      userConfirmed: true as const,
      assistantResearchComplete: true as const,
    },
  };
}
