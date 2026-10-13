export type ScoutWatchRequest = {
  symbols: string[];
  interval: "1min" | "5min";
};

export function normalizeWatchSymbols(raw: unknown): string[] {
  if (!Array.isArray(raw) || raw.length < 1 || raw.length > 5) {
    throw new Error("Scout Watch requires 1-5 TSX symbols");
  }
  const normalized = raw.map((value) => {
    const symbol = String(value || "").trim().toUpperCase();
    if (!/^[A-Z0-9.\-]{1,12}:TSX$/.test(symbol)) {
      throw new Error("Scout Watch accepts TICKER:TSX symbols only");
    }
    if (symbol === "CSU:TSX") {
      throw new Error("CSU uses the dedicated realtime bot, not Scout Watch");
    }
    return symbol;
  });
  return [...new Set(normalized)];
}

export function normalizeWatchInterval(raw: unknown): "1min" | "5min" {
  return raw === "1min" ? "1min" : "5min";
}

export function normalizeWatchRequest(body: unknown): ScoutWatchRequest {
  if (!body || typeof body !== "object") throw new Error("Scout Watch request must be an object");
  const value = body as { symbols?: unknown; interval?: unknown };
  return {
    symbols: normalizeWatchSymbols(value.symbols),
    interval: normalizeWatchInterval(value.interval),
  };
}
