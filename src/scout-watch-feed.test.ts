import assert from "node:assert/strict";
import { normalizeWatchInterval, normalizeWatchRequest, normalizeWatchSymbols } from "./scout-watch-feed";

assert.deepEqual(
  normalizeWatchSymbols(["aaa:tsx", "BBB:TSX", "aaa:tsx"]),
  ["AAA:TSX", "BBB:TSX"],
);

assert.throws(
  () => normalizeWatchSymbols(["CSU:TSX"]),
  /dedicated realtime bot/,
);

assert.throws(
  () => normalizeWatchSymbols(["NYSE:IBM"]),
  /TICKER:TSX/,
);

assert.throws(
  () => normalizeWatchSymbols(["A:TSX", "B:TSX", "C:TSX", "D:TSX", "E:TSX", "F:TSX"]),
  /1-5/,
);

assert.equal(normalizeWatchInterval("1min"), "1min");
assert.equal(normalizeWatchInterval("5min"), "5min");
assert.equal(normalizeWatchInterval("bogus"), "5min");

assert.deepEqual(
  normalizeWatchRequest({ symbols: ["AAA:TSX"], interval: "1min" }),
  { symbols: ["AAA:TSX"], interval: "1min" },
);

console.log("scout-watch-feed safety tests passed");
