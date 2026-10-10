import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import assert from 'node:assert/strict';

const html=readFileSync('public/index.html','utf8');
const start=html.indexOf('const ids=new Set(),memoryIds=new Set()');
const end=html.indexOf("if(!confirm('Replace local",start);
assert.ok(start>=0&&end>start,'backup validation code must exist');
const validation=html.slice(start,end);
function validate(data){return runInNewContext(validation+'\ntrue',{data,Date,Set,Error})}
const base=()=>({
 holdings:[{id:'csu',symbol:'CSU.TO',name:'Constellation Software'}],
 selected:'csu',
 memories:[{id:'m-123',holdingId:'csu',occurredAt:'2026-10-10T12:00:00.000Z',reviewedAt:'2026-10-10T13:00:00.000Z',action:'BUY',reason:'Testing an investment thesis',outcome:'POSITIVE',price:'2500'}]
});
assert.equal(validate(base()),true,'valid exported seed holding should restore');
const cases=[
 ['duplicate symbols',d=>d.holdings.push({id:'h-2',symbol:'CSU.TO',name:'Duplicate'})],
 ['duplicate holding IDs',d=>d.holdings.push({...d.holdings[0]})],
 ['missing selected holding',d=>d.selected='h-missing'],
 ['empty reason',d=>d.memories[0].reason='   '],
 ['bad review date',d=>d.memories[0].reviewedAt='not-a-date'],
 ['bad creation date',d=>d.memories[0].occurredAt='not-a-date'],
 ['invalid action',d=>d.memories[0].action='TRADE'],
 ['orphan memory',d=>d.memories[0].holdingId='h-missing'],
 ['duplicate memory IDs',d=>d.memories.push({...d.memories[0]})],
 ['invalid price',d=>d.memories[0].price='<script>'],
 ['invalid holding ID',d=>d.holdings[0].id='<bad>'],
];
for(const [label,change] of cases){const d=base();change(d);assert.throws(()=>validate(d),{name:'Error'},label)}
console.log('RUNLU INVEST backup validation behavior tests passed ('+(cases.length+1)+' cases)');
