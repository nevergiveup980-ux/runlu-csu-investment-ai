type Candle = { datetime: string; open: number; high: number; low: number; close: number; volume: number };

type IndicatorResult = {
  price: number;
  changePct: number | null;
  sma20: number | null;
  sma50: number | null;
  rsi14: number | null;
  macd: number | null;
  macdSignal: number | null;
  atr14: number | null;
  volumeRatio: number | null;
  support20: number | null;
  resistance20: number | null;
};

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data, null, 2), {
  status,
  headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "access-control-allow-origin": "*"
  }
});

function avg(xs: number[]): number | null {
  if (!xs.length) return null;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function ema(values: number[], period: number): number[] {
  if (values.length < period) return [];
  const k = 2 / (period + 1);
  const out: number[] = [];
  let prev = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out.push(prev);
  for (let i = period; i < values.length; i++) {
    prev = values[i] * k + prev * (1 - k);
    out.push(prev);
  }
  return out;
}

function rsi(values: number[], period = 14): number | null {
  if (values.length <= period) return null;
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const d = values[i] - values[i - 1];
    if (d >= 0) gains += d; else losses -= d;
  }
  let ag = gains / period, al = losses / period;
  for (let i = period + 1; i < values.length; i++) {
    const d = values[i] - values[i - 1];
    const g = Math.max(d, 0), l = Math.max(-d, 0);
    ag = (ag * (period - 1) + g) / period;
    al = (al * (period - 1) + l) / period;
  }
  if (al === 0) return 100;
  const rs = ag / al;
  return 100 - 100 / (1 + rs);
}

function atr(candles: Candle[], period = 14): number | null {
  if (candles.length <= period) return null;
  const trs: number[] = [];
  for (let i = 1; i < candles.length; i++) {
    const c = candles[i], p = candles[i - 1];
    trs.push(Math.max(c.high - c.low, Math.abs(c.high - p.close), Math.abs(c.low - p.close)));
  }
  let a = trs.slice(0, period).reduce((x, y) => x + y, 0) / period;
  for (let i = period; i < trs.length; i++) a = (a * (period - 1) + trs[i]) / period;
  return a;
}

function indicators(candles: Candle[]): IndicatorResult {
  const closes = candles.map(c => c.close);
  const vols = candles.map(c => c.volume).filter(Number.isFinite);
  const price = closes.at(-1)!;
  const prev = closes.length > 1 ? closes.at(-2)! : null;
  const e12 = ema(closes, 12), e26 = ema(closes, 26);
  const offset = e12.length - e26.length;
  const macdSeries = e26.map((v, i) => e12[i + offset] - v);
  const sig = ema(macdSeries, 9);
  const recent20 = candles.slice(-20);
  const v20 = vols.slice(-20);
  const avgv = avg(v20);
  return {
    price,
    changePct: prev ? ((price / prev) - 1) * 100 : null,
    sma20: closes.length >= 20 ? avg(closes.slice(-20)) : null,
    sma50: closes.length >= 50 ? avg(closes.slice(-50)) : null,
    rsi14: rsi(closes),
    macd: macdSeries.at(-1) ?? null,
    macdSignal: sig.at(-1) ?? null,
    atr14: atr(candles),
    volumeRatio: avgv && vols.at(-1) ? vols.at(-1)! / avgv : null,
    support20: recent20.length ? Math.min(...recent20.map(c => c.low)) : null,
    resistance20: recent20.length ? Math.max(...recent20.map(c => c.high)) : null
  };
}

function analyze(i: IndicatorResult) {
  let score = 0;
  const reasons: string[] = [];
  if (i.sma20 != null) {
    if (i.price > i.sma20) { score += 1; reasons.push("Price is above SMA20"); }
    else { score -= 1; reasons.push("Price is below SMA20"); }
  }
  if (i.sma20 != null && i.sma50 != null) {
    if (i.sma20 > i.sma50) { score += 1; reasons.push("SMA20 is above SMA50"); }
    else { score -= 1; reasons.push("SMA20 is below SMA50"); }
  }
  if (i.rsi14 != null) {
    if (i.rsi14 < 30) { score += 1; reasons.push("RSI14 is in an oversold zone"); }
    else if (i.rsi14 > 70) { score -= 1; reasons.push("RSI14 is in an overbought zone"); }
    else reasons.push("RSI14 is neutral");
  }
  if (i.macd != null && i.macdSignal != null) {
    if (i.macd > i.macdSignal) { score += 1; reasons.push("MACD is above its signal line"); }
    else { score -= 1; reasons.push("MACD is below its signal line"); }
  }
  if (i.volumeRatio != null && i.volumeRatio >= 1.5) reasons.push(`Volume is elevated (${i.volumeRatio.toFixed(2)}× 20-period average)`);
  const stance = score >= 2 ? "Bullish" : score <= -2 ? "Caution" : "Neutral";
  return { stance, score, reasons, disclaimer: "Research signal only; not an automatic trade instruction." };
}

async function getCandles(env: Env, interval = "1day", outputsize = 120): Promise<Candle[]> {
  const symbol = `${env.CSU_SYMBOL}:${env.CSU_EXCHANGE}`;
  const u = new URL("https://api.twelvedata.com/time_series");
  u.searchParams.set("symbol", symbol);
  u.searchParams.set("interval", interval);
  u.searchParams.set("outputsize", String(outputsize));
  u.searchParams.set("format", "JSON");
  const res = await fetch(u, { headers: { Authorization: `apikey ${env.TWELVE_DATA_API_KEY}` } });
  if (!res.ok) throw new Error(`Market data HTTP ${res.status}`);
  const data = await res.json() as { status?: string; message?: string; values?: Array<Record<string, string>> };
  if (!data.values) throw new Error(data.message || "Market data unavailable");
  return data.values.slice().reverse().map(v => ({
    datetime: v.datetime,
    open: Number(v.open), high: Number(v.high), low: Number(v.low), close: Number(v.close), volume: Number(v.volume || 0)
  })).filter(c => [c.open, c.high, c.low, c.close].every(Number.isFinite));
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/api/health") return json({ ok: true, symbol: `${env.CSU_SYMBOL}:${env.CSU_EXCHANGE}` });
      if (url.pathname === "/api/csu") {
        const interval = url.searchParams.get("interval") || "1day";
        const allowed = new Set(["1min", "5min", "15min", "30min", "1h", "1day"]);
        if (!allowed.has(interval)) return json({ error: "Unsupported interval" }, 400);
        const candles = await getCandles(env, interval, interval === "1day" ? 120 : 200);
        const ind = indicators(candles);
        return json({ symbol: `${env.CSU_SYMBOL}:${env.CSU_EXCHANGE}`, interval, asOf: candles.at(-1)?.datetime, indicators: ind, analysis: analyze(ind), candles: candles.slice(-80) });
      }
      return env.ASSETS.fetch(request);
    } catch (error) {
      console.error(JSON.stringify({ message: "request failed", error: String(error), path: url.pathname }));
      return json({ error: "Unable to load CSU market data", detail: String(error) }, 502);
    }
  }
};
