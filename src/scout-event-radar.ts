export type ScoutMaterialEventType =
  | "EARNINGS"
  | "GUIDANCE"
  | "M_AND_A"
  | "MANAGEMENT_CHANGE"
  | "REGULATORY"
  | "CAPITAL_RAISE"
  | "DIVIDEND_CHANGE"
  | "CREDIT_EVENT"
  | "LITIGATION"
  | "MATERIAL_NEWS";

export type PressReleaseLike = {
  id?: unknown;
  datetime?: unknown;
  title?: unknown;
  body?: unknown;
};

export type ScoutMaterialEvent = {
  id: string;
  type: ScoutMaterialEventType;
  title: string;
  datetime: string | null;
  sourceType: "OFFICIAL_PRESS_RELEASE";
};

const RULES: Array<[ScoutMaterialEventType, RegExp[]]> = [
  ["GUIDANCE", [/guidance/i, /outlook/i, /forecast/i]],
  ["EARNINGS", [/earnings/i, /financial results?/i, /quarterly results?/i, /annual results?/i]],
  ["M_AND_A", [/acquisition/i, /acquire[sd]?/i, /merger/i, /strategic combination/i, /takeover/i]],
  ["MANAGEMENT_CHANGE", [/chief executive/i, /chief financial/i, /ceo/i, /cfo/i, /resign(?:s|ed|ation)?/i, /appoint(?:s|ed|ment)?/i]],
  ["REGULATORY", [/regulator(?:y)?/i, /competition bureau/i, /securities commission/i, /approval/i, /investigation/i]],
  ["CAPITAL_RAISE", [/offering/i, /financing/i, /private placement/i, /public offering/i, /convertible/i]],
  ["DIVIDEND_CHANGE", [/dividend/i, /distribution/i]],
  ["CREDIT_EVENT", [/credit rating/i, /downgrade/i, /default/i, /refinanc(?:e|ing)/i, /debt covenant/i]],
  ["LITIGATION", [/lawsuit/i, /litigation/i, /legal proceedings?/i, /class action/i]],
];

const text = (value: unknown) => String(value ?? "").replace(/<[^>]*>/g, " ").replace(/s+/g, " ").trim();

export function classifyPressRelease(item: PressReleaseLike): ScoutMaterialEventType {
  const haystack = `${text(item.title)} ${text(item.body)}`;
  for (const [kind, patterns] of RULES) {
    if (patterns.some((pattern) => pattern.test(haystack))) return kind;
  }
  return "MATERIAL_NEWS";
}

export function normalizeMaterialEvent(item: PressReleaseLike): ScoutMaterialEvent | null {
  const id = text(item.id);
  const title = text(item.title);
  if (!id || !title) return null;
  const rawDatetime = text(item.datetime);
  return {
    id,
    type: classifyPressRelease(item),
    title: title.slice(0, 240),
    datetime: rawDatetime || null,
    sourceType: "OFFICIAL_PRESS_RELEASE",
  };
}


export function normalizeEventSymbols(raw: unknown): string[] {
  if (!Array.isArray(raw) || raw.length < 1 || raw.length > 3) {
    throw new Error("Scout Event Radar requires 1-3 TSX symbols");
  }
  const out: string[] = [];
  for (const value of raw) {
    const symbol = String(value || "").trim().toUpperCase();
    if (!/^[A-Z0-9.\-]{1,12}:TSX$/.test(symbol)) {
      throw new Error("Scout Event Radar accepts TICKER:TSX symbols only");
    }
    if (symbol === "CSU:TSX") {
      throw new Error("CSU uses the dedicated CSU research workflow");
    }
    if (!out.includes(symbol)) out.push(symbol);
  }
  return out;
}
