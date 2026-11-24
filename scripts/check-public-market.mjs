import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
const number = x => x == null || Number.isFinite(x);
const date = x => typeof x === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(x);
const stamp = x => typeof x === 'string' && /^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/.test(x);
const trend = x => ['Strong Uptrend','Uptrend','Mixed / Sideways','Downtrend','Strong Downtrend'].includes(x);
const entry = x => ['Favorable Area','Extended','Balanced','Weak / Risky','Neutral'].includes(x);
const mode = x => ['Intraday delayed/indicative','Daily fallback'].includes(x);
const deep = (x, fields, f) => x && typeof x === 'object' && !Array.isArray(x) && Object.keys(x).every(k=>fields.includes(k)&&f(x[k],k));
const paperFields='id signal entryDate entryPrice trend entryQuality trendConfidence return5d return10d return20d price5d price10d price20d date5d date10d date20d createdAt priceMode'.split(' ');
function paper(t){return deep(t,paperFields,(v,k)=>k==='id'?typeof v==='string'&&/^BUY-\d{4}-\d{2}-\d{2}-\d+$/.test(v): k.startsWith('date')||k==='entryDate'?date(v):k==='createdAt'?stamp(v):k==='signal'?v==='BUY':k==='trend'?trend(v):k==='entryQuality'?entry(v):k==='priceMode'?mode(v):k==='trendConfidence'?/^\d+%$/.test(v):number(v))&&t.signal==='BUY'&&date(t.entryDate)&&Number.isFinite(t.entryPrice);}
export const safePaperTrades = items => Array.isArray(items) ? items.filter(paper) : [];
export const marketReason = x => typeof x==='string' && /^(?:Trend: (?:Strong Uptrend|Uptrend|Mixed \/ Sideways|Downtrend|Strong Downtrend) \([+-]?\d+\/\d+\)|Entry quality: (?:Favorable Area|Extended|Balanced|Weak \/ Risky|Neutral)|Latest price lane: (?:Intraday delayed\/indicative|Daily fallback)|Technical buy signal: (?:BUY|DO NOT BUY)|Sell decision: (?:SELL|HOLD|HOLD \/ REVIEW|REVIEW \/ POSSIBLE SELL)|RSI14 is \d+(?:\.\d+)?|MACD is (?:above|below) signal|Price is within ~3\.5% of 20-day support|Price is more than ~8% above SMA20|RSI is elevated|Momentum and SMA20 distance are balanced|Price is not especially close to support or unusually extended|Price is more than ~5% below SMA50)$/.test(x);
const candle=x=>deep(x,'timestamp time date open high low close volume'.split(' '),(v,k)=>k==='time'?stamp(v):k==='date'?date(v):Number.isFinite(v));
const top='symbol version source updatedAt asOf dataStatus indicators analysis paperTrades paperSummary candles hourlyCandles twoHourCandles'.split(' ');
const allowed= (x,k)=>{
 switch(k){
 case 'symbol': return x==='CSU.TO';
 case 'version': return x==='1.8';
 case 'source': return x==='Public daily technical data plus best-effort delayed/indicative intraday chart data';
 case 'updatedAt':return stamp(x);
 case 'asOf':return date(x);
 case 'dataStatus':return deep(x,'quoteMode quoteSource priceAsOf refreshCadence staleAfterMinutes hourlyChartAvailable'.split(' '),(v,k)=>k==='quoteMode'?mode(v):k==='quoteSource'?/^Yahoo public (5-minute|daily) chart feed$/.test(v):k==='priceAsOf'?stamp(v):k==='refreshCadence'?v==='Every 2 hours on weekdays':k==='hourlyChartAvailable'?typeof v==='boolean':number(v));
 case 'indicators':return deep(x,'price dailyClose sma20 sma50 sma100 sma200 rsi14 macd macdSignal support20 resistance20'.split(' '),number);
 case 'analysis':return deep(x,'trend trendScore trendConfidence entryQuality technicalBuyDecision buyDecision sellDecision reasons disclaimer'.split(' '),(v,k)=>k==='trend'?trend(v):k==='entryQuality'?entry(v):k==='reasons'?Array.isArray(v)&&v.every(marketReason):k==='disclaimer'?v==='Research recommendation based on delayed/indicative public technical data. It is not a guarantee of return and does not execute trades.':k==='sellDecision'?['SELL','HOLD','HOLD / REVIEW','REVIEW / POSSIBLE SELL'].includes(v):k.endsWith('Decision')?['BUY','DO NOT BUY'].includes(v):k==='trendConfidence'?/^\d+%$/.test(v):number(v))&&x.buyDecision===x.technicalBuyDecision;
 case 'paperTrades':return Array.isArray(x)&&x.every(paper);
 case 'paperSummary':return deep(x,'total completed winRate20d avgReturn20d'.split(' '),number);
 case 'candles':case 'hourlyCandles':case 'twoHourCandles':return Array.isArray(x)&&x.every(candle);
 }
};
export function assertMarketData(d){
 if(!deep(d,top,allowed)||!top.every(k=>Object.hasOwn(d,k)))throw Error('Public data rejected: unexpected or invalid market fields');
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const files=fs.readdirSync('public').sort();
 if(files.join(',')!=='data.json,index.html,monitor.html')throw Error('Public directory must contain only the three approved market files');
 assertMarketData(JSON.parse(fs.readFileSync('public/data.json','utf8')));
 console.log('Market-only public files and data verified.');
}
