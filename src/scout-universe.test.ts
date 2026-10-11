import { buildScoutUniverse, chooseUniverseBatch } from "./scout-universe";

const universe = buildScoutUniverse([
  { symbol: "AAA", name: "Alpha Corp", exchange: "TSX", country: "Canada", type: "Common Stock" },
  { symbol: "BBB", name: "Beta Corp", exchange: "TSX", country: "Canada", type: "Common Stock" },
  { symbol: "PREF", name: "Preferred Holdings", exchange: "TSX", country: "Canada", type: "Common Stock" },
  { symbol: "ETF1", name: "Sample ETF Fund", exchange: "TSX", country: "Canada", type: "Common Stock" },
  { symbol: "USA", name: "US Corp", exchange: "NASDAQ", country: "United States", type: "Common Stock" },
  { symbol: "AAA", name: "Duplicate Alpha", exchange: "TSX", country: "Canada", type: "Common Stock" },
]);

if (universe.length !== 2) throw new Error("Universe filter should keep only two TSX common-stock research candidates");
if (universe.some((x) => x.tradeEligible)) throw new Error("Universe discovery must never grant trading eligibility");
if (universe.some((x) => !x.researchOnly)) throw new Error("Universe entries must remain research-only");

const first = chooseUniverseBatch(universe, 0, 1);
if (first.symbols[0] !== "AAA:TSX" || first.nextCursor !== 1 || first.wrapped) {
  throw new Error("First rotating Scout batch is wrong");
}

const second = chooseUniverseBatch(universe, 1, 2);
if (second.symbols.join(",") !== "BBB:TSX,AAA:TSX") throw new Error("Wrapped Scout batch is wrong");
if (second.nextCursor !== 1 || !second.wrapped) throw new Error("Wrapped cursor state is wrong");

let blocked = false;
try {
  chooseUniverseBatch(universe, 0, 9);
} catch {
  blocked = true;
}
if (!blocked) throw new Error("Scout batch larger than 8 must fail");

console.log("scout universe safety checks passed");
