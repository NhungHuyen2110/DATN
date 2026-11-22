// Real Chrome + QA API only; no response mocks or injected runtime config.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('@playwright/test');
const root=path.resolve(__dirname,'../..'),fixturePath=path.resolve(process.argv[2]||'');
assert.ok(fixturePath.startsWith(path.join(root,'.local-tmp')+path.sep));
const fixture=JSON.parse(fs.readFileSync(fixturePath,'utf8'));
const output=process.argv[3];assert.ok(output&&!fs.existsSync(output));
const base='http://127.0.0.1:18082',pagePath='/pages/admin/product-attributes.html';
(async()=>{
 const browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true});
 const cases=[];
 try {
  for(const role of ['guest','staff','customer']) {
   const context=await browser.newContext();
   await context.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
   context.setDefaultTimeout(15000);
   if(role!=='guest') assert.equal((await context.request.post(base+'/api/auth/login',{data:fixture.accounts[role]})).status(),200);
   const page=await context.newPage();await page.goto(base+pagePath,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>!document.querySelector('#review-status').textContent.includes('Đang kiểm tra'));
   assert.equal(await page.locator('#review-q').isDisabled(),true,'Unauthorized user cannot use product search');
   assert.equal((await context.request.get(base+'/api/admin/product-attributes/options')).status(),role==='guest'?401:403);
   cases.push(role+' is denied by the API and cannot use the editor');
   await context.close();
  }
  const context=await browser.newContext();
  context.setDefaultTimeout(15000);
  assert.equal((await context.request.post(base+'/api/auth/login',{data:fixture.accounts.admin})).status(),200);
  const page=await context.newPage();
  await page.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(base+pagePath,{waitUntil:'domcontentloaded'});await page.locator('#review-editor').waitFor();
  await page.waitForFunction(()=>!document.querySelector('#review-editor').disabled);
  const product=await (await context.request.get(base+'/api/products/500')).json();
  const reviews=await (await context.request.get(base+'/api/admin/products/500/verified-attributes')).json();
  assert.ok(!reviews.some(row=>row.label==='Style'&&row.canonical_id==='elegant'&&row.active),'Integration precondition: QA browser product has no active elegant fixture');
  await page.locator('#review-q').fill(product.sku);
  await page.locator('#review-search button').click();
  await page.locator('#review-results button').filter({hasText:product.sku}).click();
  await page.locator('#review-detail').waitFor({state:'visible'});
  assert.ok((await page.locator('#review-product-name').innerText()).includes(product.name));
  assert.equal(await page.locator('#review-approved').isChecked(),false);
  await page.locator('#review-label').selectOption('Style');
  await page.locator('#review-canonical').selectOption('elegant');
  const evidence='local-qa-reviewed-attributes-fixture:browser <img src=x onerror=alert(1)>';
  await page.locator('#review-source').fill(evidence);await page.locator('#review-approved').check();
  const confirmed=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/500/verified-attributes'));
  await page.locator('#review-confirm button').click();assert.equal((await confirmed).status(),200);
  await page.waitForFunction(()=>!document.querySelector('#review-editor').disabled);
  const styleItem=page.locator('#review-history li').filter({hasText:'Phong cách: Thanh lịch'});
  assert.ok((await styleItem.innerText()).includes(evidence));
  assert.equal(await styleItem.locator('img').count(),0);
  assert.equal(await page.locator('#review-approved').isChecked(),false);
  cases.push('Admin reviews a real catalog product and confirms a label with explicit unchecked-by-default consent');
  cases.push('raw evidence is rendered as text and creates no executable image element');
  const publicProduct=await (await context.request.get(base+'/api/products/500')).json();
  assert.ok(publicProduct.verified_attributes.some(fact=>fact.label==='Style'&&fact.canonical_id==='elegant'));
  assert.ok(!JSON.stringify(publicProduct).includes('onerror'));
  cases.push('public API exposes canonical label and evidence hash without private review note');
  const revoked=page.waitForResponse(r=>r.request().method()==='DELETE'&&r.url().includes('/500/verified-attributes/'));
  await styleItem.getByRole('button',{name:'Thu hồi nhãn'}).click();assert.equal((await revoked).status(),204);
  await page.waitForFunction(()=>!document.querySelector('#review-editor').disabled);
  assert.ok((await styleItem.innerText()).includes('Đã thu hồi'));
  const final=await (await context.request.get(base+'/api/products/500')).json();
  assert.ok(!final.verified_attributes.some(fact=>fact.label==='Style'&&fact.canonical_id==='elegant'));
  cases.push('Admin revocation keeps visible history and immediately removes public active label');
  assert.deepEqual(errors,[]);await context.close();
  fs.writeFileSync(output,JSON.stringify({successful:true,passed:cases.length,cases,base_url:base,
   browser:'installed Chrome',response_mocks:false,injected_runtime_config:false,
   qa_fixture_only:true,original_accounts_changed:false,serving_database_written:false},null,2)+'\n');
  console.log(JSON.stringify({successful:true,passed:cases.length,report:output}));
 } finally {await browser.close()}
})().catch(error=>require('./secure-failure.cjs')(error,fixturePath,output));
