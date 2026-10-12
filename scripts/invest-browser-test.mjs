import {readFileSync} from 'node:fs';
import {chromium,webkit} from 'playwright';
import assert from 'node:assert/strict';

const engine=process.env.INVEST_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch({headless:true});
try{
 const page=await browser.newPage(process.env.INVEST_BROWSER==='webkit'?{viewport:{width:390,height:844},isMobile:true,hasTouch:true}:{ });
 await page.route('**/api/market?**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({indicators:{price:2500,rsi14:48},analysis:{stance:'NEUTRAL'},asOf:'2026-10-10'})}));
 await page.goto('http://127.0.0.1:4173/');
 // GitHub Pages is a static, local-only preview; verify its banner and quote guard.
 const preview=await browser.newPage();
 await preview.route('https://runlu-preview.github.io/**',async route=>{
   const response=await preview.request.get('http://127.0.0.1:4173/');
   await route.fulfill({response});
 });
 await preview.goto('https://runlu-preview.github.io/');
 await preview.locator('#previewNotice').waitFor({state:'visible'});
 assert.match(await preview.locator('#marketStatus').innerText(),/Add your first holding/);
 assert.match(await preview.locator('#welcome').innerText(),/Welcome to RUNLU INVEST/);
 assert.equal(await preview.locator('#price').innerText(),'—');
 await preview.close();
 await page.locator('#newSymbol').fill('AAPL');
 await page.locator('#newName').fill('Apple Inc.');
 await page.locator('#addHolding').click();
 await page.locator('#holdingTitle').getByText('Apple Inc. · AAPL').waitFor();
 assert.match(await page.locator('#selectedSymbol').innerText(),/AAPL/);
 await page.locator('#reason').fill('Testing my investment thesis');
 await page.locator('#expectation').fill('Review in a month');
 await page.locator('#saveMemory').click();
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);
 await page.reload();
 assert.match(await page.locator('#selectedSymbol').innerText(),/AAPL/);
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);
 assert.match(await page.locator('#marketStatus').innerText(),/Market research loaded/);
 // Exercise the actual browser export and file-input import paths.
 const downloadPromise=page.waitForEvent('download');
 await page.locator('#exportBackup').click();
 const download=await downloadPromise;
 const backupPath=await download.path();
 assert.ok(backupPath,'backup should download as a file');
 await page.evaluate(()=>localStorage.removeItem('runlu-invest-v01'));
 await page.reload();
 assert.doesNotMatch(await page.locator('#holdingTitle').innerText(),/AAPL/);
 page.once('dialog',dialog=>dialog.accept());
 await page.locator('#backupFile').setInputFiles(backupPath);
 await page.locator('#holdingTitle').getByText('Apple Inc. · AAPL').waitFor();
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);
 assert.match(await page.locator('#backupStatus').innerText(),/Backup restored and verified on this device/);
 await page.reload();
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);
 // Invalid import must not overwrite an existing portfolio or memory.
 const before=await page.evaluate(()=>localStorage.getItem('runlu-invest-v01'));
 const invalid=JSON.stringify({format:'runlu-invest-backup',version:1,data:{holdings:[{id:'csu',symbol:'CSU.TO',name:'CSU'}],selected:'csu',memories:[{id:'m-bad',holdingId:'csu',occurredAt:'invalid-date',action:'BUY',reason:'broken'}]}});
 const rejected=page.waitForEvent('dialog');
 await page.locator('#backupFile').setInputFiles({name:'invalid-backup.json',mimeType:'application/json',buffer:Buffer.from(invalid)});
 const errorDialog=await rejected;
 assert.match(errorDialog.message(),/Import failed:/);
 await errorDialog.accept();
 assert.match(await page.locator('#backupStatus').innerText(),/Import failed:/);
 const after=await page.evaluate(()=>localStorage.getItem('runlu-invest-v01'));
 assert.equal(after,before,'invalid backup must preserve existing local data');
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);
 // Simulate one failed localStorage write during a valid restore.
 // The app must roll back to the previous saved portfolio.
 await page.evaluate(()=>{
   const original=Storage.prototype.setItem;
   let remaining=1;
   Storage.prototype.setItem=function(key,value){
     if(key==='runlu-invest-v01'&&remaining-->0)throw new DOMException('Simulated storage failure','QuotaExceededError');
     return original.call(this,key,value);
   };
   window.__restoreSetItem=()=>{Storage.prototype.setItem=original};
 });
 const restoreDialogs=[];
 const onRestoreDialog=async dialog=>{
   restoreDialogs.push(dialog.message());
   await dialog.accept();
 };
 page.on('dialog',onRestoreDialog);
 await page.locator('#backupFile').setInputFiles({name:'valid-restore-with-storage-error.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'runlu-invest-backup',version:1,data:{holdings:[{id:'csu',symbol:'CSU.TO',name:'Constellation Software'}],selected:'csu',memories:[]}}))});
 await page.waitForFunction(()=>document.querySelector('#backupFile').value==='');
 page.off('dialog',onRestoreDialog);
 await page.evaluate(()=>window.__restoreSetItem());
 assert.ok(restoreDialogs.some(message=>message.includes('Replace local RUNLU INVEST data')),'restore confirmation shown');
 assert.ok(restoreDialogs.some(message=>message.includes('Import failed:')),'storage failure shown');
 assert.equal(await page.evaluate(()=>localStorage.getItem('runlu-invest-v01')),before,'failed restore preserves previous backup');
 await page.reload();
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);

 console.log((process.env.INVEST_BROWSER||'chromium')+' RUNLU INVEST browser flow passed: holding, memory, reload, market, backup export/import and invalid backup and storage failure protection');
}finally{await browser.close()}
