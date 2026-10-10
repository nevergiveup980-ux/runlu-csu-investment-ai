import {readFileSync} from 'node:fs';
import {chromium} from 'playwright';
import assert from 'node:assert/strict';

const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage();
 await page.route('**/api/market?**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({indicators:{price:2500,rsi14:48},analysis:{stance:'NEUTRAL'},asOf:'2026-10-10'})}));
 await page.goto('http://127.0.0.1:4173/');
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
 page.once('dialog',dialog=>dialog.accept());
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
 await page.reload();
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);
 console.log('RUNLU INVEST browser flow passed: holding, memory, reload, market, backup export/import');
}finally{await browser.close()}
