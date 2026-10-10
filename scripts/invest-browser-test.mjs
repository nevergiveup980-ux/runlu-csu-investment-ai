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
 await page.getByText('Apple Inc.').waitFor();
 assert.match(await page.locator('#selectedSymbol').innerText(),/AAPL/);
 await page.locator('#reason').fill('Testing my investment thesis');
 await page.locator('#expectation').fill('Review in a month');
 await page.locator('#saveMemory').click();
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);
 await page.reload();
 assert.match(await page.locator('#selectedSymbol').innerText(),/AAPL/);
 assert.match(await page.locator('#timeline').innerText(),/Testing my investment thesis/);
 assert.match(await page.locator('#marketStatus').innerText(),/Market research loaded/);
 console.log('RUNLU INVEST browser flow passed: add holding, save memory, reload, market');
}finally{await browser.close()}
