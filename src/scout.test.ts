import { applyJointResearchReview, scoreScoutCandidate } from "./scout";

const strong = scoreScoutCandidate("SYNTH:TSX", {
  price: 100,
  changePct: -2,
  rsi14: 36,
  macd: 1.2,
  macdSignal: 1.0,
  sma20: 102,
  sma50: 98,
  sma200: 90,
  support20: 98,
  resistance20: 112,
  volumeRatio: 1.1,
});

if (!strong.researchRequired) throw new Error("Scout candidates must require research");
if (strong.tradeEligible) throw new Error("Scout candidates must never be directly trade eligible");
if (strong.stage !== "RESEARCH_REQUIRED") throw new Error("New candidate must enter research gate");
if (strong.tier !== "PRIORITY_RESEARCH") throw new Error("Synthetic strong candidate should rank for priority research");

let blocked = false;
try {
  applyJointResearchReview(strong, {
    researchComplete: true,
    assistantResearchComplete: true,
    userConfirmed: false,
    finalDecision: "APPROVED",
    thesis: "Synthetic thesis",
    bearCase: "Synthetic bear case",
    keyRisks: ["Synthetic risk"],
    invalidation: "Synthetic invalidation",
  });
} catch {
  blocked = true;
}
if (!blocked) throw new Error("Approval without user confirmation must fail");

const reviewed = applyJointResearchReview(strong, {
  researchComplete: true,
  assistantResearchComplete: true,
  userConfirmed: true,
  finalDecision: "APPROVED",
  thesis: "Synthetic thesis",
  bearCase: "Synthetic bear case",
  keyRisks: ["Synthetic risk"],
  invalidation: "Synthetic invalidation",
});
if (reviewed.stage !== "APPROVED_UNIVERSE") throw new Error("Joint review stage mismatch");
if (!reviewed.realtimeEligible) throw new Error("Approved universe should be realtime eligible");
if (reviewed.tradeEligible) throw new Error("Scout review must not grant trading permission");

const weak = scoreScoutCandidate("WEAK:TSX", {
  price: 80,
  changePct: -12,
  rsi14: 20,
  macd: -2,
  macdSignal: -1,
  sma20: 95,
  sma50: 100,
  sma200: 110,
  support20: 90,
  resistance20: 120,
  volumeRatio: 5,
});
if (weak.score >= strong.score) throw new Error("Risky candidate should not outrank stronger candidate");
if (!weak.riskFlags.length) throw new Error("Risky candidate should expose risk flags");

console.log("scout safety checks passed");
