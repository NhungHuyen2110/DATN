const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('@playwright/test');
const root=path.resolve(__dirname,'../..');
const fixturePath=path.resolve(process.argv[2]||'');
assert.ok(fixturePath.startsWith(path.join(root,'.local-tmp')+path.sep));
const fixture=JSON.parse(fs.readFileSync(fixturePath,'utf8'));
const output=process.argv[3];assert.ok(output&&!fs.existsSync(output));
(async()=>{
 const browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true});
 const cases=[];
 try{
  // Explicit real-model readiness precondition; do not inject browser config.
  const primer=await browser.newContext();
  let qaReady=false,qaReadinessAttempts=0;
  for(;qaReadinessAttempts<20;qaReadinessAttempts++){
   try{
    const health=await primer.request.get('http://127.0.0.1:18081/api/health/ready',{timeout:5000});
    if(health.ok()){qaReady=true;break}
   }catch{}
   await new Promise(resolve=>setTimeout(resolve,2000));
  }
  assert.ok(qaReady,'QA Business must be ready before authentication');
  assert.equal((await primer.request.post('http://127.0.0.1:18081/api/auth/login',
    {data:fixture.accounts.admin})).status(),200);
  let readinessAttempts=0,ready=false;
  for(;readinessAttempts<12;readinessAttempts++){
   const r=await primer.request.post('http://127.0.0.1:18081/api/admin/ai/retrieval-diagnostics',
     {data:{query:'nhẫn',top_k:1},timeout:20000});
   if(r.ok()){
    const d=await r.json();
    if(d.status==='ok'&&d.diagnostics?.source_ranks?.dense?.length){ready=true;break}
   }
   await new Promise(resolve=>setTimeout(resolve,5000));
  }
  assert.ok(ready,'Real retrieval model must be ready before the context scenario');
  await primer.close();
  const page=await browser.newPage();
  await page.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());
  await page.goto('http://127.0.0.1:18080/');
  await page.locator('#chat-fab').click();
  async function customerTurn(query){
   await page.locator('#chat-query').fill(query);
   const reply=page.waitForResponse(r=>new URL(r.url()).pathname==='/ai/chat',{timeout:60000});
   await page.locator('#chat-form button').click();
   const response=await reply;assert.equal(response.status(),200);
   const data=await response.json();
   await page.waitForFunction(()=>!document.querySelector('#chat-form button').disabled);
   return data;
  }
  const first=await customerTurn('sinh nhật tặng gì');
  assert.ok(first.conversation_id);assert.equal(first.products.length,3);
  const ids=first.products.map(p=>p.ProductID);
  const second=await customerTurn('tại sao lại gợi ý sản phẩm đó');
  assert.equal(second.intent,'conversation_explanation');assert.deepEqual(second.products,[]);
  assert.deepEqual(second.referenced_product_ids,ids);
  assert.equal(second.conversation_id,first.conversation_id);
  assert.equal(await page.locator('#chat-messages .chat-products>div').count(),3);
  cases.push('customer why refers to original IDs and creates no new product cards');
  const third=await customerTurn('có hỏi sản phẩm đâu mà trả lời');
  assert.equal(third.intent,'conversation_correction');assert.deepEqual(third.products,[]);
  assert.equal(await page.locator('#chat-messages .chat-products>div').count(),3);
  cases.push('customer correction produces no new search or product cards');
  const general=await customerTurn('Bạn đang nói chuyện gì vậy?');
  assert.equal(general.intent,'general_question');assert.deepEqual(general.products,[]);
  cases.push('general exchange is not automatically product search');
  for(const role of ['admin','staff']){
   const context=await browser.newContext();
   const login=await context.request.post('http://127.0.0.1:18081/api/auth/login',{data:fixture.accounts[role]});
   assert.equal(login.status(),200);
   const privatePage=await context.newPage();
   await privatePage.goto('http://127.0.0.1:18081/pages/'+(role==='admin'?'admin/dashboard.html':'staff/orders.html'));
   await privatePage.locator('#lumiere-mgmt-ai .ai-toggle').click();
   async function managementTurn(question){
    await privatePage.locator('.ai-input').fill(question);
    const reply=privatePage.waitForResponse(r=>new URL(r.url()).pathname==='/api/'+role+'/ai/chat');
    await privatePage.locator('.ai-send').click();
    const response=await reply;assert.equal(response.status(),200);
    const data=await response.json();
    await privatePage.waitForFunction(()=>!document.querySelector('.ai-send').disabled);
    return data;
   }
   const initial=await managementTurn(role==='admin'?'Những sản phẩm nào sắp hết hàng?':'Có bao nhiêu đơn chờ xử lý?');
   const explanation=await managementTurn('Tại sao kết quả như vậy?');
   assert.equal(explanation.conversation_id,initial.conversation_id);
   assert.equal(explanation.intent,'conversation_explanation');
   assert.ok(explanation.answer.includes(initial.answer));
   cases.push(role+' browser keeps authenticated conversation and explains prior aggregate');
   await context.close();
  }
  const report={successful:true,browser:'actual installed Chrome',cases,passed:cases.length,
   customer_target:'serving original-data copy on 18080',management_target:'private QA copy on 18081',
   mocked_api_responses:false,injected_runtime_config:false,serving_original_accounts_modified:false,
   natural_llm_live_verified:false,scope:'context regression; does not claim ChatGPT-like general dialogue'};
  report.real_model_readiness_attempts=readinessAttempts+1;
  report.qa_readiness_attempts=qaReadinessAttempts+1;
  fs.writeFileSync(output,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
