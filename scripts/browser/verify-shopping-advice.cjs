const {chromium}=require('@playwright/test');
const fs=require('node:fs'),assert=require('node:assert/strict');
const reportPath=process.argv[2];
assert.ok(reportPath&&!fs.existsSync(reportPath),'Choose a new report');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true});
 try{
  const page=await browser.newPage();
  await page.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  await page.goto('http://127.0.0.1:18080/');
  await page.locator('#chat-fab').click();
  await page.locator('#chat-query').fill('Lễ tình nhân tặng gì?');
  const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/ai/chat',{timeout:60000});
  await page.locator('#chat-form button').click();
  const reply=await response;assert.equal(reply.status(),200);
  const data=await reply.json();assert.equal(data.advice_intent,'gift_advice');
  assert.equal(data.products.length,3);
  await page.waitForFunction(()=>document.querySelectorAll('#chat-messages .chat-products>div').length===3);
  assert.ok((await page.locator('#chat-messages').innerText()).includes('sở thích của người nhận'));
  assert.equal(await page.locator('#chat-messages .chat-products a[href*="product-detail.html?id="]').count(),3);
  const report={successful:true,browser:'actual installed Chrome',base_url:'http://127.0.0.1:18080',
   query:'Lễ tình nhân tặng gì?',advice_intent:data.advice_intent,visible_advice:true,
   linked_product_cards:3,mocked_api_responses:false,injected_runtime_config:false,
   quality_benchmark:false,authenticated:false,writes_performed:false};
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close()}
})().catch(error=>{console.error(error.message);process.exitCode=1});
