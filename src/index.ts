import { botStatus, buildBotDecision, type BotPortfolioState, type OpenOrder } from "./csu-bot-v2";
import { createPaperLedger, simulateDecision } from "./paper-trader";
import { accountDiagnostics, toBotPortfolio, validateSnapshot, type BrokerAccountSnapshot } from "./broker-bridge";
import { createTradeProposal } from "./trade-proposal";
import { buildDecisionReviewPacket } from "./review-packet";
import { scoreScoutCandidate } from "./scout";
import { buildScoutUniverse, type StockCatalogRow } from "./scout-universe";
import { normalizeWatchRequest } from "./scout-watch-feed";
import { normalizeEventSymbols, normalizeMaterialEvent, type PressReleaseLike } from "./scout-event-radar";
import { createSessionToken, getCookie, privatePortfolioConfigured, sanitizePrivatePortfolioSnapshot, sha256Hex, verifyPrivateLogin, verifySessionToken } from "./private-portfolio";

type Candle = {
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type IndicatorResult = {
  price: number;
  changePct: number | null;
  sma20: number | null;
  sma50: number | null;
  sma100: number | null;
  sma200: number | null;
  rsi14: number | null;
  macd: number | null;
  macdSignal: number | null;
  atr14: number | null;
  volumeRatio: number | null;
  support20: number | null;
  resistance20: number | null;
};

const json = (data: unknown, status = 200, cache = "public, max-age=900") =>
  new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": cache,
      "access-control-allow-origin": "*",
    },
  });

const privateJson = (data: unknown, status = 200, extraHeaders: Record<string, string> = {}) =>
  new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, private",
      "pragma": "no-cache",
      "x-content-type-options": "nosniff",
      "x-frame-options": "DENY",
      "referrer-policy": "no-referrer",
      ...extraHeaders,
    },
  });

const PRIVATE_SESSION_COOKIE = "runlu_private_session";
const PRIVATE_SNAPSHOT_KEY = "private:portfolio:latest";
const PRIVATE_SESSION_TTL = 8 * 60 * 60;

const avg = (xs: number[]) => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;

function ema(values: number[], period: number) {
  if (values.length < period) return [];
  const k = 2 / (period + 1);
  const out: number[] = [];
  let value = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out.push(value);
  for (let i = period; i < values.length; i++) {
    value = values[i] * k + value * (1 - k);
    out.push(value);
  }
  return out;
}

function rsi(values: number[], period = 14) {
  if (values.length <= period) return null;
  let gains = 0;
  let losses = 0;
  for (let i = 1; i <= period; i++) {
    const d = values[i] - values[i - 1];
    d >= 0 ? gains += d : losses -= d;
  }
  let avgGain = gains / period;
  let avgLoss = losses / period;
  for (let i = period + 1; i < values.length; i++) {
    const d = values[i] - values[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(d, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-d, 0)) / period;
  }
  return avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
}

function atr(candles: Candle[], period = 14) {
  if (candles.length <= period) return null;
  const trueRanges: number[] = [];
  for (let i = 1; i < candles.length; i++) {
    trueRanges.push(Math.max(
      candles[i].high - candles[i].low,
      Math.abs(candles[i].high - candles[i - 1].close),
      Math.abs(candles[i].low - candles[i - 1].close),
    ));
  }
  let value = trueRanges.slice(0, period).reduce((a, b) => a + b, 0) / period;
  for (let i = period; i < trueRanges.length; i++) {
    value = (value * (period - 1) + trueRanges[i]) / period;
  }
  return value;
}

function indicators(candles: Candle[]): IndicatorResult {
  const closes = candles.map((x) => x.close);
  const volumes = candles.map((x) => x.volume).filter(Number.isFinite);
  const price = closes.at(-1)!;
  const previous = closes.at(-2) ?? null;
  const ema12 = ema(closes, 12);
  const ema26 = ema(closes, 26);
  const offset = ema12.length - ema26.length;
  const macdValues = ema26.map((x, i) => ema12[i + offset] - x);
  const signal = ema(macdValues, 9);
  const recent20 = candles.slice(-20);
  const avgVolume = avg(volumes.slice(-20));
  const sma = (n: number) => closes.length >= n ? avg(closes.slice(-n)) : null;

  return {
    price,
    changePct: previous ? ((price / previous) - 1) * 100 : null,
    sma20: sma(20),
    sma50: sma(50),
    sma100: sma(100),
    sma200: sma(200),
    rsi14: rsi(closes),
    macd: macdValues.at(-1) ?? null,
    macdSignal: signal.at(-1) ?? null,
    atr14: atr(candles),
    volumeRatio: avgVolume && volumes.at(-1) ? volumes.at(-1)! / avgVolume : null,
    support20: recent20.length ? Math.min(...recent20.map((x) => x.low)) : null,
    resistance20: recent20.length ? Math.max(...recent20.map((x) => x.high)) : null,
  };
}

function analyze(i: IndicatorResult) {
  let score = 0;
  const reasons: string[] = [];

  if (i.sma20 != null) {
    i.price > i.sma20
      ? (score++, reasons.push("Price is above SMA20"))
      : (score--, reasons.push("Price is below SMA20"));
  }
  if (i.sma20 != null && i.sma50 != null) {
    i.sma20 > i.sma50
      ? (score++, reasons.push("SMA20 is above SMA50"))
      : (score--, reasons.push("SMA20 is below SMA50"));
  }
  if (i.sma50 != null && i.sma200 != null) {
    i.sma50 > i.sma200
      ? (score++, reasons.push("Long-term trend is constructive"))
      : (score--, reasons.push("Long-term trend remains weak"));
  }
  if (i.rsi14 != null) {
    if (i.rsi14 < 35) {
      score++;
      reasons.push("RSI is near an oversold area");
    } else if (i.rsi14 > 70) {
      score--;
      reasons.push("RSI is elevated / overbought");
    } else {
      reasons.push("RSI is in a neutral range");
    }
  }
  if (i.macd != null && i.macdSignal != null) {
    i.macd > i.macdSignal
      ? (score++, reasons.push("MACD is above signal"))
      : (score--, reasons.push("MACD is below signal"));
  }

  const nearSupport = i.support20 != null && i.price <= i.support20 * 1.03;
  if (nearSupport) {
    score++;
    reasons.push("Price is close to 20-day support");
  }

  const stance = score >= 3 ? "BUY ZONE"
    : score >= 1 ? "WATCH"
      : score >= -1 ? "HOLD"
        : score >= -3 ? "CAUTION"
          : "REDUCE";

  const confidence = Math.min(90, 50 + Math.abs(score) * 10);
  return {
    stance,
    score,
    confidence: `${confidence}%`,
    reasons,
    disclaimer: "Research signal only; verify current brokerage data before any decision.",
  };
}

async function yahooDaily(): Promise<Candle[]> {
  const url = "https://query1.finance.yahoo.com/v8/finance/chart/CSU.TO?range=2y&interval=1d&events=div%2Csplits";
  const response = await fetch(url, {
    headers: { "user-agent": "Mozilla/5.0 RUNLU-CSU-Bot-V2/2.0" },
  });
  if (!response.ok) throw new Error(`Daily source HTTP ${response.status}`);
  const data: any = await response.json();
  const result = data?.chart?.result?.[0];
  const quote = result?.indicators?.quote?.[0];
  if (!result?.timestamp || !quote) throw new Error("Daily source unavailable");

  return result.timestamp
    .map((t: number, i: number) => ({
      datetime: new Date(t * 1000).toISOString().slice(0, 10),
      open: +quote.open[i],
      high: +quote.high[i],
      low: +quote.low[i],
      close: +quote.close[i],
      volume: +(quote.volume[i] || 0),
    }))
    .filter((c: Candle) => [c.open, c.high, c.low, c.close].every(Number.isFinite));
}

function normalizeScoutSymbol(raw: string) {
  const symbol = String(raw || "").trim().toUpperCase();
  if (!/^[A-Z0-9.\-]{1,12}:TSX$/.test(symbol)) {
    throw new Error("Scout V1 accepts TSX symbols in TICKER:TSX format only");
  }
  return symbol;
}

async function twelveSymbol(env: Env, symbol: string, interval: string, outputsize = 300): Promise<Candle[]> {
  if (!env.TWELVE_DATA_API_KEY) throw new Error("Market data source not configured");
  const normalized = normalizeScoutSymbol(symbol);
  const url = new URL("https://api.twelvedata.com/time_series");
  url.searchParams.set("symbol", normalized);
  url.searchParams.set("interval", interval);
  url.searchParams.set("outputsize", String(outputsize));

  const response = await fetch(url, {
    headers: { Authorization: `apikey ${env.TWELVE_DATA_API_KEY}` },
  });
  const data: any = await response.json();
  if (!data.values) throw new Error(data.message || "Market data unavailable");

  return data.values
    .slice()
    .reverse()
    .map((v: any) => ({
      datetime: v.datetime,
      open: +v.open,
      high: +v.high,
      low: +v.low,
      close: +v.close,
      volume: +(v.volume || 0),
    }))
    .filter((c: Candle) => [c.open, c.high, c.low, c.close].every(Number.isFinite));
}

async function twelve(env: Env, interval: string): Promise<Candle[]> {
  return twelveSymbol(env, "CSU:TSX", interval);
}

async function twelvePressReleases(env: Env, symbol: string) {
  if (!env.TWELVE_DATA_API_KEY) throw new Error("Market data source not configured");
  const normalized = normalizeScoutSymbol(symbol);
  const [ticker] = normalized.split(":");
  const url = new URL("https://api.twelvedata.com/press_releases");
  url.searchParams.set("symbol", ticker);
  url.searchParams.set("exchange", "TSX");
  url.searchParams.set("outputsize", "5");
  url.searchParams.set("language", "en,en-US");

  const response = await fetch(url, {
    headers: { Authorization: `apikey ${env.TWELVE_DATA_API_KEY}` },
  });
  const data: any = await response.json();
  if (!response.ok || !Array.isArray(data?.press_releases)) {
    throw new Error(data?.message || "Press release data unavailable");
  }
  return data.press_releases
    .map((item: PressReleaseLike) => normalizeMaterialEvent(item))
    .filter(Boolean);
}

async function twelveTsxUniverse(env: Env) {
  if (!env.TWELVE_DATA_API_KEY) throw new Error("Market data source not configured");
  const url = new URL("https://api.twelvedata.com/stocks");
  url.searchParams.set("exchange", "TSX");
  url.searchParams.set("country", "Canada");
  url.searchParams.set("type", "Common Stock");

  const response = await fetch(url, {
    headers: { Authorization: `apikey ${env.TWELVE_DATA_API_KEY}` },
  });
  const data: any = await response.json();
  if (!response.ok || !Array.isArray(data?.data)) {
    throw new Error(data?.message || "TSX stock catalog unavailable");
  }
  return buildScoutUniverse(data.data as StockCatalogRow[]);
}


function parseOpenOrders(url: URL): OpenOrder[] {
  const raw = url.searchParams.get("openOrders");
  if (!raw) return [];
  let value: unknown;
  try { value = JSON.parse(raw); } catch { throw new Error("openOrders must be valid JSON"); }
  if (!Array.isArray(value)) throw new Error("openOrders must be a JSON array");
  return value.map((x: any) => ({
    id: x.id == null ? undefined : String(x.id),
    symbol: String(x.symbol || ""),
    side: ["BUY", "SELL"].includes(String(x.side || "").toUpperCase()) ? String(x.side).toUpperCase() as "BUY" | "SELL" : "UNKNOWN",
    quantity: Number(x.quantity || 0),
    limitPrice: x.limitPrice == null ? null : Number(x.limitPrice),
    status: String(x.status || "OPEN"),
  }));
}

function parsePortfolio(url: URL): BotPortfolioState {
  const rawShares = Number(url.searchParams.get("shares") ?? "0");
  const rawCash = url.searchParams.has("cash") ? Number(url.searchParams.get("cash")) : null;
  const rawBuyingPower = url.searchParams.has("buyingPower") ? Number(url.searchParams.get("buyingPower")) : null;
  const rawAverageCost = url.searchParams.has("averageCost") ? Number(url.searchParams.get("averageCost")) : null;
  const rawHistoryCount = url.searchParams.has("historyCount") ? Number(url.searchParams.get("historyCount")) : null;

  if (!Number.isInteger(rawShares) || rawShares < 0 || rawShares > 3) throw new Error("shares must be an integer from 0 to 3");
  for (const [name, value] of [["cash", rawCash], ["buyingPower", rawBuyingPower], ["averageCost", rawAverageCost]] as const) {
    if (value != null && (!Number.isFinite(value) || value < 0)) throw new Error(`${name} must be a non-negative number`);
  }
  if (rawHistoryCount != null && (!Number.isInteger(rawHistoryCount) || rawHistoryCount < 0)) throw new Error("historyCount must be a non-negative integer");

  return {
    shares: rawShares,
    cash: rawCash,
    buyingPower: rawBuyingPower,
    averageCost: rawAverageCost,
    currency: url.searchParams.get("currency") || "CAD",
    openOrders: parseOpenOrders(url),
    historyCount: rawHistoryCount,
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    try {
      // Private account snapshots must never be accepted by the public preview
      // endpoint without a separately configured server-side bearer secret.
      if (url.pathname === "/api/bot/account-preview") {
        const secret = (env as Env & { CSU_SNAPSHOT_TOKEN?: string }).CSU_SNAPSHOT_TOKEN;
        if (!secret || request.headers.get("Authorization") !== `Bearer ${secret}`) {
          return new Response(JSON.stringify({ error: "Private account preview unavailable" }), {
            status: 403,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }
      }
      if (url.pathname === "/api/private/status" && request.method === "GET") {
        const privateEnv = env as Env & {
          PRIVATE_PORTFOLIO_USERNAME?: string;
          PRIVATE_PORTFOLIO_PASSWORD_HASH?: string;
          PRIVATE_PORTFOLIO_PASSWORD_SALT?: string;
          PRIVATE_SESSION_SECRET?: string;
          PRIVATE_SNAPSHOT_UPLOAD_TOKEN?: string;
          PRIVATE_PORTFOLIO?: { get(key: string): Promise<string | null> };
        };
        const authConfigured = Boolean(
          privateEnv.PRIVATE_PORTFOLIO_USERNAME
          && privateEnv.PRIVATE_PORTFOLIO_PASSWORD_HASH
          && privateEnv.PRIVATE_PORTFOLIO_PASSWORD_SALT
          && privateEnv.PRIVATE_SESSION_SECRET,
        );
        const storageConfigured = Boolean(privateEnv.PRIVATE_PORTFOLIO);
        const uploadConfigured = Boolean(privateEnv.PRIVATE_SNAPSHOT_UPLOAD_TOKEN);
        let snapshotAvailable = false;
        let snapshotFetchedAt: string | null = null;
        if (storageConfigured) {
          try {
            const raw = await privateEnv.PRIVATE_PORTFOLIO!.get(PRIVATE_SNAPSHOT_KEY);
            if (raw) {
              const parsed = JSON.parse(raw);
              snapshotAvailable = true;
              snapshotFetchedAt = typeof parsed?.fetchedAt === "string" ? parsed.fetchedAt : null;
            }
          } catch {
            snapshotAvailable = false;
          }
        }
        return privateJson({
          product: "RUNLU Private Portfolio",
          mode: "PRIVATE_READ_ONLY",
          ready: authConfigured && storageConfigured && uploadConfigured,
          authConfigured,
          storageConfigured,
          uploadConfigured,
          snapshotAvailable,
          snapshotFetchedAt,
          permissions: {
            viewPortfolio: true,
            approveTrade: false,
            placeOrder: false,
            modifyOrder: false,
            cancelOrder: false,
          },
        });
      }

      if (url.pathname === "/api/private/login" && request.method === "POST") {
        const privateEnv = env as Env & {
          PRIVATE_PORTFOLIO_USERNAME?: string;
          PRIVATE_PORTFOLIO_PASSWORD_HASH?: string;
          PRIVATE_PORTFOLIO_PASSWORD_SALT?: string;
          PRIVATE_SESSION_SECRET?: string;
          PRIVATE_PORTFOLIO?: {
            get(key: string): Promise<string | null>;
            put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
            delete(key: string): Promise<void>;
          };
        };
        if (!privatePortfolioConfigured(privateEnv)) {
          return privateJson({ error: "Private portfolio is not configured" }, 503);
        }

        const ip = request.headers.get("CF-Connecting-IP") || "unknown";
        const ipHash = await sha256Hex(ip);
        const attemptKey = "private:login:" + ipHash;
        const priorRaw = await privateEnv.PRIVATE_PORTFOLIO!.get(attemptKey);
        const prior = Math.max(0, Number(priorRaw || "0") || 0);
        if (prior >= 5) {
          return privateJson({ error: "Too many login attempts. Try again later." }, 429);
        }

        let body: { username?: string; password?: string };
        try {
          body = await request.json() as typeof body;
        } catch {
          return privateJson({ error: "Invalid login request" }, 400);
        }
        const ok = await verifyPrivateLogin(
          String(body.username || ""),
          String(body.password || ""),
          privateEnv,
        );
        if (!ok) {
          await privateEnv.PRIVATE_PORTFOLIO!.put(attemptKey, String(prior + 1), { expirationTtl: 900 });
          return privateJson({ error: "Invalid username or password" }, 401);
        }

        await privateEnv.PRIVATE_PORTFOLIO!.delete(attemptKey);
        const token = await createSessionToken(
          privateEnv.PRIVATE_PORTFOLIO_USERNAME!,
          privateEnv.PRIVATE_SESSION_SECRET!,
          Math.floor(Date.now() / 1000),
          PRIVATE_SESSION_TTL,
        );
        return privateJson(
          { ok: true, expiresInSeconds: PRIVATE_SESSION_TTL },
          200,
          {
            "set-cookie": `${PRIVATE_SESSION_COOKIE}=${token}; Max-Age=${PRIVATE_SESSION_TTL}; Path=/api/private; HttpOnly; Secure; SameSite=Strict`,
          },
        );
      }

      if (url.pathname === "/api/private/logout" && request.method === "POST") {
        return privateJson(
          { ok: true },
          200,
          {
            "set-cookie": `${PRIVATE_SESSION_COOKIE}=; Max-Age=0; Path=/api/private; HttpOnly; Secure; SameSite=Strict`,
          },
        );
      }

      if (url.pathname === "/api/private/session" && request.method === "GET") {
        const privateEnv = env as Env & {
          PRIVATE_PORTFOLIO_USERNAME?: string;
          PRIVATE_SESSION_SECRET?: string;
        };
        if (!privateEnv.PRIVATE_PORTFOLIO_USERNAME || !privateEnv.PRIVATE_SESSION_SECRET) {
          return privateJson({ authenticated: false }, 503);
        }
        const token = getCookie(request, PRIVATE_SESSION_COOKIE);
        const authenticated = token
          ? await verifySessionToken(
              token,
              privateEnv.PRIVATE_PORTFOLIO_USERNAME,
              privateEnv.PRIVATE_SESSION_SECRET,
            )
          : false;
        return privateJson({ authenticated }, authenticated ? 200 : 401);
      }

      if (url.pathname === "/api/private/portfolio" && request.method === "GET") {
        const privateEnv = env as Env & {
          PRIVATE_PORTFOLIO_USERNAME?: string;
          PRIVATE_SESSION_SECRET?: string;
          PRIVATE_PORTFOLIO?: { get(key: string): Promise<string | null> };
        };
        if (!privateEnv.PRIVATE_PORTFOLIO || !privateEnv.PRIVATE_PORTFOLIO_USERNAME || !privateEnv.PRIVATE_SESSION_SECRET) {
          return privateJson({ error: "Private portfolio is not configured" }, 503);
        }
        const token = getCookie(request, PRIVATE_SESSION_COOKIE);
        const authenticated = token
          ? await verifySessionToken(
              token,
              privateEnv.PRIVATE_PORTFOLIO_USERNAME,
              privateEnv.PRIVATE_SESSION_SECRET,
            )
          : false;
        if (!authenticated) return privateJson({ error: "Authentication required" }, 401);

        const raw = await privateEnv.PRIVATE_PORTFOLIO.get(PRIVATE_SNAPSHOT_KEY);
        if (!raw) return privateJson({ error: "No private portfolio snapshot is available yet" }, 404);
        let snapshot: unknown;
        try {
          snapshot = JSON.parse(raw);
        } catch {
          return privateJson({ error: "Stored portfolio snapshot is invalid" }, 500);
        }
        return privateJson({
          mode: "PRIVATE_READ_ONLY",
          portfolio: snapshot,
          permissions: {
            viewPortfolio: true,
            approveTrade: false,
            placeOrder: false,
            modifyOrder: false,
            cancelOrder: false,
          },
        });
      }

      if (url.pathname === "/api/private/snapshot" && request.method === "POST") {
        const privateEnv = env as Env & {
          PRIVATE_SNAPSHOT_UPLOAD_TOKEN?: string;
          PRIVATE_PORTFOLIO?: { put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void> };
        };
        const secret = privateEnv.PRIVATE_SNAPSHOT_UPLOAD_TOKEN;
        if (!secret || request.headers.get("Authorization") !== `Bearer ${secret}`) {
          return privateJson({ error: "Private snapshot upload unavailable" }, 403);
        }
        if (!privateEnv.PRIVATE_PORTFOLIO) {
          return privateJson({ error: "Private portfolio storage is not configured" }, 503);
        }

        let raw: unknown;
        try {
          raw = await request.json();
        } catch {
          return privateJson({ error: "Invalid portfolio snapshot JSON" }, 400);
        }

        let snapshot;
        try {
          snapshot = sanitizePrivatePortfolioSnapshot(raw);
        } catch (error) {
          return privateJson({ error: String(error) }, 422);
        }
        const fetchedMs = Date.parse(snapshot.fetchedAt);
        const now = Date.now();
        if (fetchedMs > now + 5 * 60 * 1000 || fetchedMs < now - 30 * 60 * 1000) {
          return privateJson({ error: "Portfolio snapshot is outside the accepted freshness window" }, 422);
        }

        await privateEnv.PRIVATE_PORTFOLIO.put(
          PRIVATE_SNAPSHOT_KEY,
          JSON.stringify(snapshot),
          { expirationTtl: 7 * 24 * 60 * 60 },
        );
        return privateJson({
          ok: true,
          storedAt: new Date().toISOString(),
          fetchedAt: snapshot.fetchedAt,
          positions: snapshot.positions.length,
          tradeEligible: false,
          brokerSubmissionEnabled: false,
        });
      }

      if (url.pathname === "/api/health") {
        return json({
          ok: true,
          product: "RUNLU CSU Investment AI",
          bot: "CSU Bot V2",
          scout: "RUNLU Scout V1",
          scoutMode: "DISCOVERY_RESEARCH_ONLY",
          mode: "PAPER_ONLY",
          liveTrading: false,
        }, 200, "no-store");
      }

      if (url.pathname === "/api/bot/status") {
        return json(botStatus(), 200, "no-store");
      }

      if (url.pathname === "/api/bot/account-preview" && request.method === "POST") {
        let snapshot: BrokerAccountSnapshot;
        try {
          snapshot = await request.json() as BrokerAccountSnapshot;
        } catch {
          return json({ error: "Invalid broker snapshot JSON", decision: "HOLD", liveTradingEnabled: false }, 400, "no-store");
        }

        const validation = validateSnapshot(snapshot);
        if (!validation.valid) {
          return json({
            mode: "READ_ONLY_SIMULATION",
            decision: "HOLD",
            reason: "Broker snapshot failed safety validation",
            validation,
            liveTradingEnabled: false,
          }, 422, "no-store");
        }

        const portfolio = toBotPortfolio(snapshot);
        const diagnostics = accountDiagnostics(snapshot);
        const candles = await yahooDaily();
        if (!candles.length) return json({ error: "No market data returned", decision: "HOLD" }, 404, "no-store");
        const ind = indicators(candles);
        const decision = buildBotDecision(ind, portfolio);
        const before = createPaperLedger(portfolio);
        const after = simulateDecision(before, decision, ind.price);

        return new Response(JSON.stringify({
          symbol: "CSU.TO",
          mode: "READ_ONLY_SIMULATION",
          asOf: candles.at(-1)?.datetime,
          broker: diagnostics,
          validation,
          portfolio,
          indicators: ind,
          decision,
          paper: { before, after },
          safety: {
            placeOrder: false,
            modifyOrder: false,
            cancelOrder: false,
            liveTradingEnabled: false,
          },
          notice: "Account-aware simulation only. No real broker order is sent.",
        }), { status: 200, headers: { "content-type": "application/json", "cache-control": "no-store" } });
      }

      if (url.pathname === "/api/bot/trade-proposal" && request.method === "POST") {
        const secret = (env as Env & { CSU_SNAPSHOT_TOKEN?: string }).CSU_SNAPSHOT_TOKEN;
        if (!secret || request.headers.get("Authorization") !== `Bearer ${secret}`) {
          return new Response(JSON.stringify({ error: "Private trade proposal unavailable" }), {
            status: 403,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }
        let body: { snapshot: BrokerAccountSnapshot; limitPriceCAD: number; expiresAt: string };
        try {
          body = await request.json() as typeof body;
        } catch {
          return json({ error: "Invalid proposal request JSON" }, 400, "no-store");
        }
        const validation = validateSnapshot(body.snapshot);
        if (!validation.valid) return json({ error: "Broker snapshot failed safety validation", validation }, 422, "no-store");
        const portfolio = toBotPortfolio(body.snapshot);
        const candles = await yahooDaily();
        if (!candles.length) return json({ error: "No market data returned" }, 404, "no-store");
        const ind = indicators(candles);
        const decision = buildBotDecision(ind, portfolio);
        const proposal = createTradeProposal(crypto.randomUUID(), decision, portfolio, Number(body.limitPriceCAD), body.expiresAt);
        const reviewPacket = proposal ? buildDecisionReviewPacket(proposal, decision, portfolio) : null;
        return new Response(JSON.stringify({
          symbol: "CSU.TO",
          mode: "HUMAN_REVIEW_REQUIRED",
          validation,
          decision,
          proposal,
          reviewPacket,
          brokerSubmitted: false,
          notice: proposal
            ? "Proposal created for human review. No brokerage order has been submitted."
            : "No executable proposal was created. No brokerage order has been submitted.",
        }), { status: 200, headers: { "content-type": "application/json", "cache-control": "no-store" } });
      }

      if (url.pathname === "/api/bot/realtime-proposal" && request.method === "POST") {
        const secret = (env as Env & { CSU_SNAPSHOT_TOKEN?: string }).CSU_SNAPSHOT_TOKEN;
        if (!secret || request.headers.get("Authorization") !== `Bearer ${secret}`) {
          return new Response(JSON.stringify({ error: "Private realtime proposal unavailable" }), {
            status: 403,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        let body: { snapshot: BrokerAccountSnapshot; expiresAt: string; interval?: "1min" | "5min" };
        try {
          body = await request.json() as typeof body;
        } catch {
          return new Response(JSON.stringify({ error: "Invalid realtime proposal JSON" }), {
            status: 400,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        const validation = validateSnapshot(body.snapshot);
        if (!validation.valid) {
          return new Response(JSON.stringify({ error: "Broker snapshot failed safety validation", validation }), {
            status: 422,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        const interval = body.interval === "5min" ? "5min" : "1min";
        const candles = await twelve(env, interval);
        if (!candles.length) {
          return new Response(JSON.stringify({ error: "No realtime market data returned" }), {
            status: 404,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        const ind = indicators(candles);
        const portfolio = toBotPortfolio(body.snapshot);
        const decision = buildBotDecision(ind, portfolio);
        const proposal = createTradeProposal(
          crypto.randomUUID(),
          decision,
          portfolio,
          ind.price,
          body.expiresAt,
        );
        const reviewPacket = proposal ? buildDecisionReviewPacket(proposal, decision, portfolio) : null;

        return new Response(JSON.stringify({
          symbol: "CSU.TO",
          mode: "REALTIME_LITE_HUMAN_REVIEW",
          interval,
          marketDataAsOf: candles.at(-1)?.datetime,
          indicators: ind,
          validation,
          decision,
          proposal,
          reviewPacket,
          brokerSubmitted: false,
          notice: proposal
            ? "Realtime-lite candidate created for human review. No brokerage order has been submitted."
            : "Realtime-lite scan produced no executable proposal.",
        }), {
          status: 200,
          headers: { "content-type": "application/json", "cache-control": "no-store" },
        });
      }

      if (url.pathname === "/api/scout/universe" && request.method === "GET") {
        const secret = (env as Env & { CSU_SNAPSHOT_TOKEN?: string }).CSU_SNAPSHOT_TOKEN;
        if (!secret || request.headers.get("Authorization") !== `Bearer ${secret}`) {
          return new Response(JSON.stringify({ error: "Private Scout universe unavailable" }), {
            status: 403,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        const universe = await twelveTsxUniverse(env);
        return new Response(JSON.stringify({
          product: "RUNLU Scout V1",
          mode: "RESEARCH_UNIVERSE_ONLY",
          exchange: "TSX",
          primaryFocus: "CSU.TO",
          count: universe.length,
          universe,
          policy: {
            researchOnly: true,
            tradeEligible: false,
            automaticTrading: false,
          },
          notice: "Catalog discovery only. Membership in this universe grants no trading authority.",
        }), {
          status: 200,
          headers: { "content-type": "application/json", "cache-control": "no-store" },
        });
      }

      if (url.pathname === "/api/scout/watch-events" && request.method === "POST") {
        const secret = (env as Env & { CSU_SNAPSHOT_TOKEN?: string }).CSU_SNAPSHOT_TOKEN;
        if (!secret || request.headers.get("Authorization") !== `Bearer ${secret}`) {
          return new Response(JSON.stringify({ error: "Private Scout Event Radar unavailable" }), {
            status: 403,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        let body: unknown;
        try {
          body = await request.json();
        } catch {
          return json({ error: "Invalid Scout Event Radar JSON" }, 400, "no-store");
        }

        let symbols: string[];
        try {
          symbols = normalizeEventSymbols((body as { symbols?: unknown })?.symbols);
        } catch (error) {
          return json({ error: String(error) }, 400, "no-store");
        }

        const observations: { symbol: string; events: unknown[] }[] = [];
        const errors: { symbol: string; error: string }[] = [];

        for (const symbol of symbols) {
          try {
            observations.push({
              symbol,
              events: await twelvePressReleases(env, symbol),
            });
          } catch (error) {
            errors.push({ symbol, error: String(error) });
          }
        }

        return new Response(JSON.stringify({
          product: "RUNLU Scout Event Radar",
          mode: "WATCH_EVENT_RESEARCH_ONLY",
          sourceType: "OFFICIAL_PRESS_RELEASE",
          observations,
          errors,
          policy: {
            researchOnly: true,
            tradeEligible: false,
            brokerSubmissionEnabled: false,
            userReviewRequired: true,
            csuHandledSeparately: true,
          },
          notice: "Official press-release observations only. Events may reopen research but cannot authorize or place a trade.",
        }), {
          status: 200,
          headers: { "content-type": "application/json", "cache-control": "no-store" },
        });
      }

      if (url.pathname === "/api/scout/watch-quotes" && request.method === "POST") {
        const secret = (env as Env & { CSU_SNAPSHOT_TOKEN?: string }).CSU_SNAPSHOT_TOKEN;
        if (!secret || request.headers.get("Authorization") !== `Bearer ${secret}`) {
          return new Response(JSON.stringify({ error: "Private Scout Watch quotes unavailable" }), {
            status: 403,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        let body: unknown;
        try {
          body = await request.json();
        } catch {
          return json({ error: "Invalid Scout Watch JSON" }, 400, "no-store");
        }

        let watch;
        try {
          watch = normalizeWatchRequest(body);
        } catch (error) {
          return json({ error: String(error) }, 400, "no-store");
        }

        const observations: { symbol: string; price: number; marketDataAsOf: string | undefined }[] = [];
        const errors: { symbol: string; error: string }[] = [];

        for (const symbol of watch.symbols) {
          try {
            const candles = await twelveSymbol(env, symbol, watch.interval, 2);
            const latest = candles.at(-1);
            if (!latest || !Number.isFinite(latest.close) || latest.close <= 0) {
              throw new Error("No valid latest price");
            }
            observations.push({
              symbol,
              price: latest.close,
              marketDataAsOf: latest.datetime,
            });
          } catch (error) {
            errors.push({ symbol, error: String(error) });
          }
        }

        return new Response(JSON.stringify({
          product: "RUNLU Scout Watch",
          mode: "WATCH_OBSERVATION_RESEARCH_ONLY",
          interval: watch.interval,
          observations,
          errors,
          policy: {
            researchOnly: true,
            tradeEligible: false,
            brokerSubmissionEnabled: false,
            csuHandledSeparately: true,
          },
          notice: "Quote observations only. No brokerage account data is accepted and no order can be created.",
        }), {
          status: 200,
          headers: { "content-type": "application/json", "cache-control": "no-store" },
        });
      }

      if (url.pathname === "/api/scout/scan" && request.method === "POST") {
        const secret = (env as Env & { CSU_SNAPSHOT_TOKEN?: string }).CSU_SNAPSHOT_TOKEN;
        if (!secret || request.headers.get("Authorization") !== `Bearer ${secret}`) {
          return new Response(JSON.stringify({ error: "Private Scout scan unavailable" }), {
            status: 403,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        let body: { symbols?: string[] };
        try {
          body = await request.json() as typeof body;
        } catch {
          return new Response(JSON.stringify({ error: "Invalid Scout scan JSON" }), {
            status: 400,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        if (!Array.isArray(body.symbols) || body.symbols.length < 1 || body.symbols.length > 8) {
          return new Response(JSON.stringify({ error: "Scout V1 requires 1-8 TSX symbols" }), {
            status: 400,
            headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }

        const uniqueSymbols = [...new Set(body.symbols.map(normalizeScoutSymbol))];
        const candidates: any[] = [];
        const errors: { symbol: string; error: string }[] = [];

        for (const symbol of uniqueSymbols) {
          try {
            const candles = await twelveSymbol(env, symbol, "1day", 260);
            if (candles.length < 50) throw new Error("Insufficient daily history for Scout");
            const market = indicators(candles);
            const candidate = scoreScoutCandidate(symbol, market);
            candidates.push({
              ...candidate,
              marketDataAsOf: candles.at(-1)?.datetime,
            });
          } catch (error) {
            errors.push({ symbol, error: String(error) });
          }
        }

        candidates.sort((a, b) => b.score - a.score);
        return new Response(JSON.stringify({
          product: "RUNLU Scout V1",
          mode: "DISCOVERY_RESEARCH_ONLY",
          primaryFocus: "CSU.TO",
          scanned: uniqueSymbols.length,
          candidates,
          errors,
          policy: {
            researchRequired: true,
            directTradingAllowed: false,
            autoPromotionAllowed: false,
            jointResearchRequired: true,
            explicitUserConfirmationRequired: true,
          },
          notice: "Scout ranks research candidates only. It cannot create broker orders or grant trading eligibility.",
        }), {
          status: 200,
          headers: { "content-type": "application/json", "cache-control": "no-store" },
        });
      }

      if (url.pathname === "/api/bot/simulate") {
        if (request.method !== "GET") return json({ error: "Simulation endpoint is GET-only." }, 405, "no-store");
        const portfolio = parsePortfolio(url);
        const candles = await yahooDaily();
        if (!candles.length) return json({ error: "No market data returned" }, 404, "no-store");
        const ind = indicators(candles);
        const decision = buildBotDecision(ind, portfolio);
        const before = createPaperLedger(portfolio);
        const after = simulateDecision(before, decision, ind.price);
        return json({
          symbol: "CSU.TO",
          mode: "SIMULATION_ONLY",
          asOf: candles.at(-1)?.datetime,
          portfolio,
          indicators: ind,
          decision,
          paper: { before, after },
          notice: "Read-only simulation. No real order is placed, changed, or cancelled.",
        }, 200, "no-store");
      }

      if (url.pathname === "/api/bot/preview") {
        if (request.method !== "GET") {
          return json({ error: "Bot preview is GET-only." }, 405, "no-store");
        }
        const portfolio = parsePortfolio(url);
        const candles = await yahooDaily();
        if (!candles.length) return json({ error: "No market data returned" }, 404, "no-store");
        const ind = indicators(candles);
        const decision = buildBotDecision(ind, portfolio);

        return json({
          symbol: "CSU.TO",
          strategy: "ADAPTIVE_SWING",
          asOf: candles.at(-1)?.datetime,
          portfolio,
          indicators: ind,
          decision,
          notice: "Preview only. No broker order is created, modified, or cancelled.",
        }, 200, "no-store");
      }

      if (url.pathname === "/api/csu") {
        const interval = url.searchParams.get("interval") || "1day";
        let candles: Candle[];
        let source: string;

        if (interval === "1day") {
          candles = await yahooDaily();
          source = "Yahoo Finance chart (unofficial, delayed/historical)";
        } else if (["1min", "5min", "1h"].includes(interval)) {
          candles = await twelve(env, interval);
          source = "Twelve Data intraday";
        } else {
          return json({
            error: "2H will be enabled by aggregating 1H once a reliable feed is available",
          }, 400);
        }

        const ind = indicators(candles);
        return json({
          symbol: "CSU.TO",
          interval,
          source,
          asOf: candles.at(-1)?.datetime,
          indicators: ind,
          analysis: analyze(ind),
          candles: candles.slice(-520),
        });
      }

      if (url.pathname.startsWith("/api/trade") || url.pathname.startsWith("/api/order")) {
        return json({
          error: "Live broker writes remain disabled in CSU Bot V2.",
          mode: "PAPER_ONLY",
        }, 403, "no-store");
      }

      return env.ASSETS.fetch(request);
    } catch (error) {
      return json({
        error: "Unable to complete CSU Bot request",
        detail: String(error),
      }, 502, "no-store");
    }
  },
};
