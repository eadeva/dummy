const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1280,height:1000}});
await page.goto(require('node:url').pathToFileURL(process.argv[2]).href);
await page.locator('details').evaluateAll(ds=>ds.forEach(d=>d.open=true));
for(const table of await page.locator('table').all()) assert.equal(await table.locator('input').count(),await table.locator('tr').first().locator('th').count());
const cards=await page.locator('.cards').allTextContents();
const table=page.locator('table').filter({has:page.getByRole('columnheader',{name:'Test',exact:true})});
await table.getByRole('searchbox',{name:'Filter Class',exact:true}).fill('PARSER');
assert.equal(await table.locator('tr[hidden]').count(),2);
await table.getByRole('searchbox',{name:'Filter Result',exact:true}).fill('failed');
assert.equal(await table.locator('tr[hidden]').count(),3);
await table.getByRole('searchbox',{name:'Filter Test',exact:true}).fill('no-match');
assert.equal(await table.locator('tr[hidden]').count(),4);
for(const input of await table.locator('input').all()) await input.fill('');
assert.equal(await table.locator('tr[hidden]').count(),0);
assert.deepEqual(await page.locator('.cards').allTextContents(),cards);

await page.setViewportSize({width:390,height:844});

assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
console.log('All table filters: combined, case-insensitive, no-match, clear, totals preserved; mobile layout passed');
await browser.close();
})();
