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
  ["GUIDANCE", [/\bguidance\b/i, /\boutlook\b/i, /\bforecast\b/i]],
  ["EARNINGS", [/\bearnings\b/i, /\bfinancial results?\b/i, /\bquarterly results?\b/i, /\bannual results?\b/i]],
  ["M_AND_A", [/\bacquisition\b/i, /\bacquire[sd]?\b/i, /\bmerger\b/i, /\bstrategic combination\b/i, /\btakeover\b/i]],
  ["MANAGEMENT_CHANGE", [/\bchief executive\b/i, /\bchief financial\b/i, /\bceo\b/i, /\bcfo\b/i, /\bresign(?:s|ed|ation)?\b/i, /\bappoint(?:s|ed|ment)?\b/i]],
  ["REGULATORY", [/\bregulator(?:y)?\b/i, /\bcompetition bureau\b/i, /\bsecurities commission\b/i, /\bapproval\b/i, /\binvestigation\b/i]],
  ["CAPITAL_RAISE", [/\boffering\b/i, /\bfinancing\b/i, /\bprivate placement\b/i, /\bpublic offering\b/i, /\bconvertible\b/i]],
  ["DIVIDEND_CHANGE", [/\bdividend\b/i, /\bdistribution\b/i]],
  ["CREDIT_EVENT", [/\bcredit rating\b/i, /\bdowngrade\b/i, /\bdefault\b/i, /\brefinanc(?:e|ing)\b/i, /\bdebt covenant\b/i]],
  ["LITIGATION", [/\blawsuit\b/i, /\blitigation\b/i, /\blegal proceedings?\b/i, /\bclass action\b/i]],
];

const text = (value: unknown) =>
  String(value ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

export function classifyPressRelease(item: PressReleaseLike): ScoutMaterialEventType {
  const haystack = text(item.title) + " " + text(item.body);
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
