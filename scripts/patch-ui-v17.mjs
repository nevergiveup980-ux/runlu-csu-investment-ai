import fs from 'node:fs';

const path = 'public/index.html';
let html = fs.readFileSync(path, 'utf8');

function replaceOnce(from, to, label) {
  if (!html.includes(from)) throw new Error(`UI patch target not found: ${label}`);
  html = html.replace(from, to);
}

replaceOnce('CSU Investment AI V1.6', 'CSU Investment AI V1.7', 'version title');
replaceOnce('Constellation Software · TSX: CSU · zero-cost data mode',
  'Constellation Software · TSX: CSU · zero-cost intraday + daily research mode',
  'subtitle');

replaceOnce('<div class="muted">Data status</div><div class="big">Daily</div>',
  '<div class="muted">Data status</div><div class="big" id="dataStatus">CHECKING</div>',
  'data status field');

replaceOnce("let range=22,interval='1day',mode='candles',all=[];",
  "let range=22,interval='1day',mode='candles',all=[],daily=[],oneHour=[],twoHour=[];",
  'chart state');

replaceOnce("const rows=all.slice(-range);",
  "const factor=interval==='1h'?7:interval==='2h'?4:1,rows=all.slice(-(range*factor));",
  'interval-aware range');

replaceOnce(
  "document.querySelectorAll('#intervals button').forEach(b=>b.onclick=()=>{if(b.dataset.interval!=='1day'){alert('A reliable free CSU intraday feed is still being evaluated. Daily remains active.');return}interval='1day';draw()});",
  "document.querySelectorAll('#intervals button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#intervals button').forEach(x=>x.classList.remove('active'));b.classList.add('active');interval=b.dataset.interval;all=interval==='1h'?oneHour:interval==='2h'?twoHour:daily;draw()});",
  'interval buttons');

replaceOnce("all=d.candles||[];",
  "daily=d.candles||[];oneHour=d.hourlyCandles||[];twoHour=d.twoHourCandles||[];all=daily;",
  'load chart datasets');

replaceOnce(
  "$('asof').textContent='Market data as of '+(d.asOf||'—')+' · refreshed '+new Date(d.updatedAt).toLocaleString();",
  "const ds=d.dataStatus||{},updated=new Date(d.updatedAt),age=(Date.now()-updated.getTime())/60000,stale=age>Number(ds.staleAfterMinutes||190);$('dataStatus').textContent=stale?'STALE DATA ⚠️':'ROBOT ACTIVE ✓';$('asof').textContent='Latest quote '+(ds.priceAsOf?new Date(ds.priceAsOf).toLocaleString():'—')+' · robot refresh '+updated.toLocaleString()+' · '+(ds.quoteMode||'Daily');",
  'robot status');

fs.writeFileSync(path, html);
console.log('Applied CSU V1.7 UI patch: 1H/2H charts + robot status.');
