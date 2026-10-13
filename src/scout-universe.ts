/** RUNLU Scout universe discovery: metadata only, never a trading universe. */

export type StockCatalogRow = {
  symbol?: string;
  name?: string;
  currency?: string;
  exchange?: string;
  mic_code?: string;
  country?: string;
  type?: string;
  access?: {
    global?: string;
    plan?: string;
    plan_business?: string;
  };
};

export type ScoutUniverseEntry = {
  symbol: string;
  providerSymbol: string;
  name: string;
  exchange: string;
  country: string;
  type: string;
  researchOnly: true;
  tradeEligible: false;
};

const BLOCKED_NAME_WORDS = [
  "WARRANT",
  "RIGHT",
  "DEBENTURE",
  "PREFERRED",
  "PREF ",
  "ETF",
  "FUND",
];

export function buildScoutUniverse(rows: StockCatalogRow[], max = 600): ScoutUniverseEntry[] {
  if (!Array.isArray(rows)) throw new Error("Stock catalog must be an array");
  if (!Number.isInteger(max) || max < 1 || max > 2000) throw new Error("Invalid Scout universe cap");

  const seen = new Set<string>();
  const out: ScoutUniverseEntry[] = [];

  for (const row of rows) {
    const raw = String(row?.symbol || "").trim().toUpperCase();
    const exchange = String(row?.exchange || "").trim().toUpperCase();
    const country = String(row?.country || "").trim();
    const type = String(row?.type || "").trim();
    const name = String(row?.name || "").trim();

    if (!raw || !/^[A-Z0-9.\-]{1,12}$/.test(raw)) continue;
    if (exchange !== "TSX") continue;
    if (country && !/^(CANADA|CA)$/i.test(country)) continue;
    if (type && type.toUpperCase() !== "COMMON STOCK") continue;

    const upperName = name.toUpperCase();
    if (BLOCKED_NAME_WORDS.some((word) => upperName.includes(word))) continue;

    const providerSymbol = `${raw}:TSX`;
    if (seen.has(providerSymbol)) continue;
    seen.add(providerSymbol);

    out.push({
      symbol: raw,
      providerSymbol,
      name,
      exchange: "TSX",
      country: country || "Canada",
      type: type || "Common Stock",
      researchOnly: true,
      tradeEligible: false,
    });
    if (out.length >= max) break;
  }

  return out.sort((a, b) => a.providerSymbol.localeCompare(b.providerSymbol));
}

export function chooseUniverseBatch(
  universe: ScoutUniverseEntry[],
  cursor: number,
  batchSize = 8,
) {
  if (!Array.isArray(universe) || universe.length === 0) {
    return { symbols: [] as string[], nextCursor: 0, wrapped: false };
  }
  if (!Number.isInteger(cursor) || cursor < 0) throw new Error("Invalid Scout cursor");
  if (!Number.isInteger(batchSize) || batchSize < 1 || batchSize > 8) {
    throw new Error("Scout batch size must be 1-8");
  }

  const start = cursor % universe.length;
  const symbols: string[] = [];
  for (let i = 0; i < Math.min(batchSize, universe.length); i++) {
    symbols.push(universe[(start + i) % universe.length].providerSymbol);
  }
  const rawNext = start + symbols.length;
  return {
    symbols,
    nextCursor: rawNext % universe.length,
    wrapped: rawNext >= universe.length,
  };
}
