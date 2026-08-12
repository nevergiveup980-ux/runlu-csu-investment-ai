import fs from 'node:fs';
const url='https://query1.finance.yahoo.com/v8/finance/chart/CSU.TO?range=2y&interval=1d&events=div%2Csplits';
const r=await fetch(url,{headers:{'User-Agent':'Mozilla/5.0 RUNLU-CSU-Research/1.5'}});if(!r.ok)throw new Error(`HTTP ${r.status}`);const d=await r.json(),x=d?.chart?.result?.[0],q=x?.indicators?.quote?.[0];if(!x?.timestamp||!q)throw new Error('No CSU data');
const candles=x.timestamp.map((t,i)=>({date:new Date(t*1000).toISOString().slice(0,10),open:+q.open[i],high:+q.high[i],low:+q.low[i],close:+q.close[i],volume:+(q.volume[i]||0)})).filter(c=>[c.open,c.high,c.low,c.close].every(Number.isFinite));
const avg=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null, closes=candles.map(c=>c.close), sm=n=>closes.length>=n?avg(closes.slice(-n)):null;
function ema(v,p){if(v.length<p)return[];let z=avg(v.slice(0,p)),o=[z],k=2/(p+1);for(let i=p;i<v.length;i++){z=v[i]*k+z*(1-k);o.push(z)}return o}
function rsi(v,p=14){if(v.length<=p)return null;let g=0,l=0;for(let i=1;i<=p;i++){let z=v[i]-v[i-1];z>=0?g+=z:l-=z}let ag=g/p,al=l/p;for(let i=p+1;i<v.length;i++){let z=v[i]-v[i-1];ag=(ag*(p-1)+Math.max(z,0))/p;al=(al*(p-1)+Math.max(-z,0))/p}return al===0?100:100-100/(1+ag/al)}
const e12=ema(closes,12),e26=ema(closes,26),off=e12.length-e26.length,ms=e26.map((v,i)=>e12[i+off]-v),sg=ema(ms,9),recent=candles.slice(-20),price=closes.at(-1),ind={price,sma20:sm(20),sma50:sm(50),sma100:sm(100),sma200:sm(200),rsi14:rsi(closes),macd:ms.at(-1),macdSignal:sg.at(-1),support20:Math.min(...recent.map(c=>c.low)),resistance20:Math.max(...recent.map(c=>c.high))};
const trendSignals=[];if(ind.sma20!=null)trendSignals.push(price>ind.sma20?1:-1);if(ind.sma20!=null&&ind.sma50!=null)trendSignals.push(ind.sma20>ind.sma50?1:-1);if(ind.sma50!=null&&ind.sma200!=null)trendSignals.push(ind.sma50>ind.sma200?1:-1);if(ind.sma200!=null)trendSignals.push(price>ind.sma200?1:-1);if(ind.macd!=null&&ind.macdSignal!=null)trendSignals.push(ind.macd>ind.macdSignal?1:-1);
const trendScore=trendSignals.reduce((a,b)=>a+b,0),agreement=trendSignals.length?Math.abs(trendScore)/trendSignals.length:0,trendConfidence=`${Math.round(Math.min(90,50+agreement*40))}%`;
const trend=trendScore>=4?'Strong Uptrend':trendScore>=2?'Uptrend':trendScore<=-4?'Strong Downtrend':trendScore<=-2?'Downtrend':'Mixed / Sideways';
const supportDistance=(price-ind.support20)/price,ma20Distance=ind.sma20?(price-ind.sma20)/ind.sma20:null,ma50Distance=ind.sma50?(price-ind.sma50)/ind.sma50:null;
let entryQuality='Neutral';const entryReasons=[];
if(supportDistance<=0.035){entryQuality='Favorable Area';entryReasons.push('Price is within ~3.5% of 20-day support')}else if(ma20Distance!=null&&ma20Distance>0.08){entryQuality='Extended';entryReasons.push('Price is more than ~8% above SMA20')}else if(ind.rsi14!=null&&ind.rsi14>=65){entryQuality='Extended';entryReasons.push('RSI is elevated')}else if(ind.rsi14!=null&&ind.rsi14>=35&&ind.rsi14<=55&&ma20Distance!=null&&Math.abs(ma20Distance)<=0.04){entryQuality='Balanced';entryReasons.push('Momentum and SMA20 distance are balanced')}else entryReasons.push('Price is not especially close to support or unusually extended');
if(ma50Distance!=null&&ma50Distance<-.05){entryQuality='Weak / Risky';entryReasons.push('Price is more than ~5% below SMA50')}
let buyDecision='DO NOT BUY',sellDecision='HOLD';
if((trend==='Strong Uptrend'||trend==='Uptrend')&&(entryQuality==='Favorable Area'||entryQuality==='Balanced')&&ind.rsi14<65)buyDecision='BUY';
if(entryQuality==='Extended'||trend==='Mixed / Sideways')buyDecision='DO NOT BUY';
if(trend==='Downtrend'||trend==='Strong Downtrend')buyDecision='DO NOT BUY';
const breakdown=(ind.sma50!=null&&price<ind.sma50)&&(ind.macd!=null&&ind.macdSignal!=null&&ind.macd<ind.macdSignal);
const severeBreak=(ind.sma200!=null&&price<ind.sma200)&&(trend==='Strong Downtrend');
if(severeBreak||breakdown)sellDecision='SELL';
else if(trend==='Strong Uptrend'||trend==='Uptrend')sellDecision='HOLD';
else if(trend==='Mixed / Sideways')sellDecision='HOLD / REVIEW';
else sellDecision='REVIEW / POSSIBLE SELL';
const reasons=[`Trend: ${trend} (${trendScore>0?'+':''}${trendScore}/${trendSignals.length})`,`Entry quality: ${entryQuality}`,...entryReasons,`Buy decision: ${buyDecision}`,`Sell decision: ${sellDecision}`];if(ind.rsi14!=null)reasons.push(`RSI14 is ${ind.rsi14.toFixed(1)}`);if(ind.macd!=null&&ind.macdSignal!=null)reasons.push(ind.macd>ind.macdSignal?'MACD is above signal':'MACD is below signal');
fs.mkdirSync('public',{recursive:true});fs.writeFileSync('public/data.json',JSON.stringify({symbol:'CSU.TO',source:'Delayed/historical public chart feed',updatedAt:new Date().toISOString(),asOf:candles.at(-1)?.date,indicators:ind,analysis:{trend,trendScore,trendConfidence,entryQuality,buyDecision,sellDecision,reasons,disclaimer:'Research recommendation based on delayed/historical technical data. It is not a guarantee of return and does not execute trades.'},candles},null,2));