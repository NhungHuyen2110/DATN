// Real browser, real QA copy of all original data. No injected API config or mocked responses.
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const {chromium}=require('@playwright/test');
const root=path.resolve(__dirname,'../..');
const fixturePath=path.resolve(process.argv[2]||'');
const reportPath=path.resolve(process.argv[3]||'');
assert.ok(fixturePath.startsWith(path.join(root,'.local-tmp')+path.sep));
assert.ok(!fs.existsSync(reportPath),'Choose a new report');
const fixture=JSON.parse(fs.readFileSync(fixturePath,'utf8'));
assert.equal(fixture.synthetic_accounts_only,true);
const base='http://127.0.0.1:18081';
(async()=>{
 const browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true});
 const cases=[];
 try{
  const guest=await browser.newContext();
  for(const role of ['admin','staff']){
   const r=await guest.request.post(base+'/api/'+role+'/ai/chat',{data:{message:'Tồn kho'}});
   assert.equal(r.status(),401);cases.push('guest denied '+role+' AI');
  }
  await guest.close();
  for(const role of ['admin','staff','customer']){
   const context=await browser.newContext();
   const page=await context.newPage();
   await page.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());
   await page.goto(base+'/pages/login.html');
   await page.getByLabel('Email').fill(fixture.accounts[role].email);
   await page.locator('#password').fill(fixture.accounts[role].password);
   const logged=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/login');
   await page.getByRole('button',{name:'ĐĂNG NHẬP',exact:true}).click();
   const loginStatus=(await logged).status();
   assert.equal(loginStatus,200,role+' QA login HTTP '+loginStatus);
   await page.waitForURL(url=>!url.pathname.endsWith('/login.html'));
   cases.push(role+' browser login on original-data QA');
   if(role==='customer'){
    for(const denied of ['admin','staff']){
     assert.equal((await context.request.post(base+'/api/'+denied+'/ai/chat',{data:{message:'Tồn kho'}})).status(),403);
     cases.push('customer denied '+denied+' AI');
    }
   }else{
    if(role==='staff'){
     assert.equal((await context.request.post(base+'/api/admin/ai/chat',{data:{message:'Doanh thu'}})).status(),403);
     cases.push('staff denied admin AI');
    }
    await page.goto(base+'/pages/'+(role==='admin'?'admin/dashboard.html':'staff/orders.html'));
    await page.locator('#lumiere-mgmt-ai .ai-toggle').click();
    await page.locator('#lumiere-mgmt-ai .ai-input').fill(role==='staff'?'Có bao nhiêu đơn chờ xử lý?':'Những sản phẩm nào sắp hết hàng?');
    const reply=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/'+role+'/ai/chat');
    await page.locator('#lumiere-mgmt-ai .ai-send').click();
    const response=await reply;assert.equal(response.status(),200);
    const data=await response.json();
    assert.ok(typeof data.answer==='string'&&data.answer.length>10);
    if(role==='staff'){
     assert.equal(data.intent,'order_statistics');
     assert.equal(data.data.value,fixture.expected_pending_orders);
    }else{
     assert.equal(data.intent,'inventory_statistics');
     assert.equal(data.data.total_products,500);
    }
    await page.waitForFunction(()=>!document.querySelector('#lumiere-mgmt-ai .ai-send').disabled);
    assert.ok((await page.locator('#lumiere-mgmt-ai .ai-message.bot').last().innerText()).includes(data.answer));
    cases.push(role+' chatbot correct /api route, SQL aggregate and visible answer');
   }
   await context.close();
  }
  const page=await browser.newPage();
  await page.goto(base+'/');
  await page.locator('#chat-fab').click();
  await page.locator('#chat-query').fill('Top 3 nhẫn dưới 8 triệu');
  const reply=page.waitForResponse(r=>new URL(r.url()).pathname==='/ai/chat',{timeout:60000});
  await page.locator('#chat-form button').click();
  const response=await reply;assert.equal(response.status(),200);
  const data=await response.json();assert.equal(data.products.length,3);
  for(const product of data.products){assert.ok(Number(product.Price)<8000000&&product.Stock>0)}
  await page.waitForFunction(()=>document.querySelectorAll('#chat-messages .chat-products>div').length===3);
  cases.push('homepage customer AI actual three products and budget/stock');
  await page.goto(base+'/pages/products.html');
  await page.locator('.lai-launch').click();
  await page.locator('#lai-query').fill('Top 10 nhẫn dưới 8 triệu');
  const topTen=page.waitForResponse(r=>new URL(r.url()).pathname==='/ai/chat',{timeout:60000});
  await page.locator('.lai-form button').click();
  const tenResponse=await topTen;assert.equal(tenResponse.status(),200);
  assert.equal((await tenResponse.json()).products.length,10);
  await page.waitForFunction(()=>document.querySelectorAll('.lai-product').length===10);
  assert.equal(await page.locator('.lai-product>a[href*="product-detail.html?id="]').count(),10);
  assert.equal(await page.locator('.lai-product img').count(),10);
  assert.ok((await page.locator('.lai-products').innerText()).includes('Còn '));
  cases.push('product widget displays all Top 10 with actual SKU photos, links and stock');
  // Establish the catalog-ready precondition before injecting a chat-only fault.
  await page.locator('#catalog-results .catalog-card').first().waitFor({state:'visible',timeout:60000});
  await page.route('**/ai/chat',r=>r.abort());
  await page.locator('#lai-query').fill('Top 1 nhẫn');
  await page.locator('.lai-form button').click();
  await page.locator('.lai-error').waitFor();
  assert.ok((await page.locator('.lai-error').innerText()).includes('Bạn vẫn có thể'));
  assert.ok(await page.locator('#catalog-results .catalog-card').first().isVisible());
  cases.push('chat network failure gives shopping-safe message and catalog remains visible');
  const report={successful:true,browser:'actual installed Chrome',base_url:base,
   scope:'QA copy of 500 original products and 12 original orders; three synthetic QA accounts',
   injected_runtime_config:false,mocked_api_responses:false,serving_original_accounts_modified:false,
   cases,passed:cases.length,qa_login_session_writes:true,production_accessed:false};
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close()}
})().catch(error=>{console.error(error.message);process.exitCode=1});
