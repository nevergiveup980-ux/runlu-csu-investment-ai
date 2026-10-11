import { botStatus, buildBotDecision, type BotPortfolioState, type OpenOrder } from "./csu-bot-v2";
import { createPaperLedger, simulateDecision } from "./paper-trader";
import { accountDiagnostics, toBotPortfolio, validateSnapshot, type BrokerAccountSnapshot } from "./broker-bridge";
import { createTradeProposal } from "./trade-proposal";
import { buildDecisionReviewPacket } from "./review-packet";

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

async function twelve(env: Env, interval: string): Promise<Candle[]> {
  if (!env.TWELVE_DATA_API_KEY) throw new Error("Intraday data source not configured");
  const url = new URL("https://api.twelvedata.com/time_series");
  url.searchParams.set("symbol", "CSU:TSX");
  url.searchParams.set("interval", interval);
  url.searchParams.set("outputsize", "300");

  const response = await fetch(url, {
    headers: { Authorization: `apikey ${env.TWELVE_DATA_API_KEY}` },
  });
  const data: any = await response.json();
  if (!data.values) throw new Error(data.message || "Intraday data unavailable");

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
      if (url.pathname === "/api/health") {
        return json({
          ok: true,
          product: "RUNLU CSU Investment AI",
          bot: "CSU Bot V2",
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
        } else if (interval === "1h") {
          candles = await twelve(env, "1h");
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
