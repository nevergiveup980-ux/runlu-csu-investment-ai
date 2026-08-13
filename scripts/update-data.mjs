import fs from 'node:fs';

const DAILY_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/CSU.TO?range=2y&interval=1d&events=div%2Csplits';
const QUOTE_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/CSU.TO?range=1d&interval=5m&includePrePost=false&events=div%2Csplits';
const HOURLY_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/CSU.TO?range=1y&interval=1h&includePrePost=false&events=div%2Csplits';
const HEADERS = { 'User-Agent': 'Mozilla/5.0 RUNLU-CSU-Research/1.7' };

async function fetchChart(url, label) {
  const r = await fetch(url, { headers: HEADERS });
  if (!r.ok) throw new Error(`${label} HTTP ${r.status}`);
  const d = await r.json();
  const x = d?.chart?.result?.[0];
  if (!x?.timestamp?.length) throw new Error(`No ${label} CSU data`);
  return x;
}

function parseOhlc(chart) {
  const q = chart?.indicators?.quote?.[0];
  if (!q) return [];
  return chart.timestamp.map((t, i) => {
    const open = q.open?.[i], high = q.high?.[i], low = q.low?.[i], close = q.close?.[i];
    if (![open, high, low, close].every(Number.isFinite)) return null;
    return {
      timestamp: t,
      time: new Date(t * 1000).toISOString(),
      open, high, low, close,
      volume: Number.isFinite(q.volume?.[i]) ? q.volume[i] : 0,
    };
  }).filter(Boolean);
}

const torontoDateFmt = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Toronto',
  year: 'numeric', month: '2-digit', day: '2-digit',
});
function torontoDate(timestamp) {
  const parts = Object.fromEntries(torontoDateFmt.formatToParts(new Date(timestamp * 1000))
    .filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function aggregate2h(rows) {
  const out = [];
  let i = 0;
  while (i < rows.length) {
    const day = torontoDate(rows[i].timestamp);
    const dayRows = [];
    while (i < rows.length && torontoDate(rows[i].timestamp) === day) dayRows.push(rows[i++]);
    for (let j = 0; j < dayRows.length; j += 2) {
      const group = dayRows.slice(j, j + 2);
      out.push({
        timestamp: group[0].timestamp,
        time: group[0].time,
        open: group[0].open,
        high: Math.max(...group.map(r => r.high)),
        low: Math.min(...group.map(r => r.low)),
        close: group.at(-1).close,
        volume: group.reduce((s, r) => s + (r.volume || 0), 0),
      });
    }
  }
  return out;
}

const daily = await fetchChart(DAILY_URL, 'daily');
const dailyRows = parseOhlc(daily).map(r => ({ ...r, date: torontoDate(r.timestamp) }));
if (dailyRows.length < 20) throw new Error('Insufficient CSU daily candles');

let quotePoint = null;
try {
  const ix = await fetchChart(QUOTE_URL, 'intraday quote');
  const points = parseOhlc(ix);
  quotePoint = points.at(-1) || null;
} catch (error) {
  console.warn(`Intraday quote unavailable; using daily fallback: ${error.message}`);
}

let hourlyCandles = [];
let twoHourCandles = [];
try {
  const hx = await fetchChart(HOURLY_URL, 'hourly');
  hourlyCandles = parseOhlc(hx);
  twoHourCandles = aggregate2h(hourlyCandles);
} catch (error) {
  console.warn(`Hourly chart feed unavailable: ${error.message}`);
}

const avg = a => a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
const closes = dailyRows.map(c => c.close);
const sm = n => closes.length >= n ? avg(closes.slice(-n)) : null;
function ema(v, p) {
  if (v.length < p) return [];
  let z = avg(v.slice(0, p)), out = [z], k = 2 / (p + 1);
  for (let i = p; i < v.length; i++) { z = v[i] * k + z * (1 - k); out.push(z); }
  return out;
}
function rsi(v, p = 14) {
  if (v.length <= p) return null;
  let g = 0, l = 0;
  for (let i = 1; i <= p; i++) { const z = v[i] - v[i - 1]; z >= 0 ? g += z : l -= z; }
  let ag = g / p, al = l / p;
  for (let i = p + 1; i < v.length; i++) {
    const z = v[i] - v[i - 1];
    ag = (ag * (p - 1) + Math.max(z, 0)) / p;
    al = (al * (p - 1) + Math.max(-z, 0)) / p;
  }
  return al === 0 ? 100 : 100 - 100 / (1 + ag / al);
}

const e12 = ema(closes, 12), e26 = ema(closes, 26), off = e12.length - e26.length;
const ms = e26.map((v, i) => e12[i + off] - v), sg = ema(ms, 9);
const recent = dailyRows.slice(-20);
const dailyPrice = closes.at(-1);
const price = quotePoint?.close ?? dailyPrice;
const priceAsOf = quotePoint?.time ?? dailyRows.at(-1)?.time;
const quoteMode = quotePoint ? 'Intraday delayed/indicative' : 'Daily fallback';
const quoteSource = quotePoint ? 'Yahoo public 5-minute chart feed' : 'Yahoo public daily chart feed';

const ind = {
  price,
  dailyClose: dailyPrice,
  sma20: sm(20), sma50: sm(50), sma100: sm(100), sma200: sm(200),
  rsi14: rsi(closes), macd: ms.at(-1), macdSignal: sg.at(-1),
  support20: Math.min(...recent.map(c => c.low)),
  resistance20: Math.max(...recent.map(c => c.high)),
};

const trendSignals = [];
if (ind.sma20 != null) trendSignals.push(price > ind.sma20 ? 1 : -1);
if (ind.sma20 != null && ind.sma50 != null) trendSignals.push(ind.sma20 > ind.sma50 ? 1 : -1);
if (ind.sma50 != null && ind.sma200 != null) trendSignals.push(ind.sma50 > ind.sma200 ? 1 : -1);
if (ind.sma200 != null) trendSignals.push(price > ind.sma200 ? 1 : -1);
if (ind.macd != null && ind.macdSignal != null) trendSignals.push(ind.macd > ind.macdSignal ? 1 : -1);
const trendScore = trendSignals.reduce((a, b) => a + b, 0);
const agreement = trendSignals.length ? Math.abs(trendScore) / trendSignals.length : 0;
const trendConfidence = `${Math.round(Math.min(90, 50 + agreement * 40))}%`;
const trend = trendScore >= 4 ? 'Strong Uptrend' : trendScore >= 2 ? 'Uptrend' : trendScore <= -4 ? 'Strong Downtrend' : trendScore <= -2 ? 'Downtrend' : 'Mixed / Sideways';

const supportDistance = (price - ind.support20) / price;
const ma20Distance = ind.sma20 ? (price - ind.sma20) / ind.sma20 : null;
const ma50Distance = ind.sma50 ? (price - ind.sma50) / ind.sma50 : null;
let entryQuality = 'Neutral';
const entryReasons = [];
if (supportDistance <= 0.035) {
  entryQuality = 'Favorable Area'; entryReasons.push('Price is within ~3.5% of 20-day support');
} else if (ma20Distance != null && ma20Distance > 0.08) {
  entryQuality = 'Extended'; entryReasons.push('Price is more than ~8% above SMA20');
} else if (ind.rsi14 != null && ind.rsi14 >= 65) {
  entryQuality = 'Extended'; entryReasons.push('RSI is elevated');
} else if (ind.rsi14 != null && ind.rsi14 >= 35 && ind.rsi14 <= 55 && ma20Distance != null && Math.abs(ma20Distance) <= 0.04) {
  entryQuality = 'Balanced'; entryReasons.push('Momentum and SMA20 distance are balanced');
} else {
  entryReasons.push('Price is not especially close to support or unusually extended');
}
if (ma50Distance != null && ma50Distance < -0.05) {
  entryQuality = 'Weak / Risky'; entryReasons.push('Price is more than ~5% below SMA50');
}

let buyDecision = 'DO NOT BUY', sellDecision = 'HOLD';
if ((trend === 'Strong Uptrend' || trend === 'Uptrend') && (entryQuality === 'Favorable Area' || entryQuality === 'Balanced') && ind.rsi14 < 65) buyDecision = 'BUY';
if (entryQuality === 'Extended' || trend === 'Mixed / Sideways' || trend === 'Downtrend' || trend === 'Strong Downtrend') buyDecision = 'DO NOT BUY';
const breakdown = (ind.sma50 != null && price < ind.sma50) && (ind.macd != null && ind.macdSignal != null && ind.macd < ind.macdSignal);
const severeBreak = (ind.sma200 != null && price < ind.sma200) && trend === 'Strong Downtrend';
if (severeBreak || breakdown) sellDecision = 'SELL';
else if (trend === 'Strong Uptrend' || trend === 'Uptrend') sellDecision = 'HOLD';
else if (trend === 'Mixed / Sideways') sellDecision = 'HOLD / REVIEW';
else sellDecision = 'REVIEW / POSSIBLE SELL';

const reasons = [
  `Trend: ${trend} (${trendScore > 0 ? '+' : ''}${trendScore}/${trendSignals.length})`,
  `Entry quality: ${entryQuality}`,
  ...entryReasons,
  `Latest price lane: ${quoteMode}`,
  `Buy decision: ${buyDecision}`,
  `Sell decision: ${sellDecision}`,
];
if (ind.rsi14 != null) reasons.push(`RSI14 is ${ind.rsi14.toFixed(1)}`);
if (ind.macd != null && ind.macdSignal != null) reasons.push(ind.macd > ind.macdSignal ? 'MACD is above signal' : 'MACD is below signal');

let old = {};
try { old = JSON.parse(fs.readFileSync('public/data.json', 'utf8')); } catch {}
let paperTrades = Array.isArray(old.paperTrades) ? old.paperTrades : [];
const pct = (a, b) => a && b ? ((b / a) - 1) * 100 : null;
const asOf = dailyRows.at(-1)?.date;
paperTrades = paperTrades.map(t => {
  const idx = dailyRows.findIndex(c => c.date === t.entryDate);
  if (idx < 0) return t;
  const result = { ...t };
  for (const n of [5, 10, 20]) {
    const c = dailyRows[idx + n];
    if (c) { result[`price${n}d`] = c.close; result[`return${n}d`] = pct(t.entryPrice, c.close); result[`date${n}d`] = c.date; }
  }
  return result;
});
const active = paperTrades.some(t => t.return20d == null);
if (buyDecision === 'BUY' && !active) {
  paperTrades.push({
    id: `BUY-${asOf}-${Date.now()}`, signal: 'BUY', entryDate: asOf, entryPrice: price,
    trend, entryQuality, trendConfidence,
    return5d: null, return10d: null, return20d: null,
    createdAt: new Date().toISOString(), priceMode: quoteMode,
  });
}
paperTrades = paperTrades.slice(-20);
const completed = paperTrades.filter(t => t.return20d != null);
const wins = completed.filter(t => t.return20d > 0).length;
const paperSummary = {
  total: paperTrades.length,
  completed: completed.length,
  winRate20d: completed.length ? wins / completed.length * 100 : null,
  avgReturn20d: completed.length ? avg(completed.map(t => t.return20d)) : null,
};

const updatedAt = new Date().toISOString();
fs.mkdirSync('public', { recursive: true });
fs.writeFileSync('public/data.json', JSON.stringify({
  symbol: 'CSU.TO',
  version: '1.7',
  source: 'Public daily technical data plus best-effort delayed/indicative intraday chart data',
  updatedAt,
  asOf,
  dataStatus: {
    quoteMode,
    quoteSource,
    priceAsOf,
    refreshCadence: 'Every 2 hours on weekdays',
    staleAfterMinutes: 190,
    hourlyChartAvailable: hourlyCandles.length > 0,
  },
  indicators: ind,
  analysis: {
    trend, trendScore, trendConfidence, entryQuality, buyDecision, sellDecision, reasons,
    disclaimer: 'Research recommendation based on delayed/indicative public technical data. It is not a guarantee of return and does not execute trades.',
  },
  paperTrades,
  paperSummary,
  candles: dailyRows,
  hourlyCandles,
  twoHourCandles,
}, null, 2));

console.log(`CSU V1.7 refresh complete: price=${price} mode=${quoteMode} hourly=${hourlyCandles.length} twoHour=${twoHourCandles.length} priceAsOf=${priceAsOf}`);