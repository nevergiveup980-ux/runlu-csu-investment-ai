import { normalizeWatchInterval, normalizeWatchRequest, normalizeWatchSymbols } from "./scout-watch-feed";

const equal = (actual: unknown, expected: unknown, message: string) => {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(message);
};

const throws = (fn: () => unknown, needle: string) => {
  let blocked = false;
  try {
    fn();
  } catch (error) {
    blocked = String(error).includes(needle);
  }
  if (!blocked) throw new Error(`Expected failure containing: ${needle}`);
};

equal(
  normalizeWatchSymbols(["aaa:tsx", "BBB:TSX", "aaa:tsx"]),
  ["AAA:TSX", "BBB:TSX"],
  "Scout Watch should normalize and dedupe TSX symbols",
);

throws(() => normalizeWatchSymbols(["CSU:TSX"]), "dedicated realtime bot");
throws(() => normalizeWatchSymbols(["NYSE:IBM"]), "TICKER:TSX");
throws(
  () => normalizeWatchSymbols(["A:TSX", "B:TSX", "C:TSX", "D:TSX", "E:TSX", "F:TSX"]),
  "1-5",
);

if (normalizeWatchInterval("1min") !== "1min") throw new Error("1min should remain 1min");
if (normalizeWatchInterval("5min") !== "5min") throw new Error("5min should remain 5min");
if (normalizeWatchInterval("bogus") !== "5min") throw new Error("Unknown interval should fail safe to 5min");

equal(
  normalizeWatchRequest({ symbols: ["AAA:TSX"], interval: "1min" }),
  { symbols: ["AAA:TSX"], interval: "1min" },
  "Scout Watch request normalization mismatch",
);

console.log("scout-watch-feed safety tests passed");
