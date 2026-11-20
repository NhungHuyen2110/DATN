/** Native CDP smoke test. Start a FRESH serve_browser_fixture.py and separate Chrome profile. */
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";

const base = "http://127.0.0.1:18001";
const evidence = "frontend/test-results/safe-cleanup";
const tabs = await fetch("http://127.0.0.1:19222/json/list").then(r => r.json());
const tab = tabs.find(item => item.type === "page");
assert.ok(tab, "Start Chrome with remote debugging on port 19222");
const socket = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let nextId = 0;
const pending = new Map();
const exceptions = [];
const verified = [];
socket.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  if (message.id) {
    const waiter = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) waiter.reject(new Error(JSON.stringify(message.error)));
    else waiter.resolve(message.result);
  } else if (message.method === "Runtime.exceptionThrown") {
    exceptions.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
  }
};
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await cdp("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}
async function wait(expression, label = expression) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Timeout: ${label}; URL=${await evaluate("location.href")}; body=${await evaluate("document.body.innerText.slice(-1800)")}`);
}
async function navigate(path, selector) {
  await cdp("Page.navigate", { url: base + path });
  await wait(`location.pathname === ${JSON.stringify(path.split("?")[0])} && !!document.querySelector(${JSON.stringify(selector)})`);
}
async function click(selector) {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
}
async function fill(selector, value, event = "input") {
  await evaluate(`(() => { const node = document.querySelector(${JSON.stringify(selector)}); node.value = ${JSON.stringify(value)}; node.dispatchEvent(new Event(${JSON.stringify(event)}, {bubbles:true})); })()`);
}
async function api(expression) { return evaluate(`window.LUMIERE_API.${expression}`); }
function pass(label) { verified.push(label); console.log("PASS", label); }
async function login(role) {
  await navigate("/pages/login.html", "#auth-form");
  await fill("#email", `${role}@example.com`);
  await fill("#password", "Browser-Test-123!");
  await click("#auth-submit");
  await wait(`location.pathname === ${JSON.stringify(role === "customer" ? "/pages/account.html" : role === "staff" ? "/pages/staff/orders.html" : "/pages/admin/dashboard.html")} && !!document.querySelector(${JSON.stringify(role === "customer" ? "#profile-form" : "#console-body .panel")})`);
}
async function logout() {
  await click("#nav-logout");
  await wait('location.pathname === "/pages/login.html" && !!document.querySelector("#auth-form")');
}
async function screenshot(name) {
  const { data } = await cdp("Page.captureScreenshot", { format: "png" });
  await writeFile(`${evidence}/${name}.png`, Buffer.from(data, "base64"));
}

try {
  await mkdir(evidence, { recursive: true });
  await cdp("Page.enable");
  await cdp("Runtime.enable");
  await cdp("Network.enable");
  await cdp("Network.clearBrowserCookies");
  await cdp("Page.addScriptToEvaluateOnNewDocument", { source: "window.LUMIERE_API_BASE = location.origin;" });
  await cdp("Page.addScriptToEvaluateOnNewDocument", { source: `
    window.__requests = [];
    const originalFetch = window.fetch;
    window.fetch = (...args) => {
      window.__requests.push({url:String(args[0]),method:args[1]?.method || 'GET'});
      return originalFetch(...args);
    };
  ` });
  await cdp("Network.setBlockedURLs", { urls: ["*images.unsplash.com*", "*127.0.0.1:8000*", "*localhost:8000*"] });
  await navigate("/pages/products.html", "#catalog-results .catalog-card");
  await screenshot("guest-catalog");
  await cdp("Page.navigate", { url: base + "/pages/admin/dashboard.html" });
  await wait('location.pathname === "/pages/login.html" && !!document.querySelector("#auth-form")');
  pass("Guest catalog loads with AI offline; protected admin page redirects");

  await navigate("/pages/register.html", "#auth-form");
  for (const [selector, value] of Object.entries({ "#full_name": "Browser Registration", "#phone": "0901234567", "#email": `browser-${Date.now()}@example.com`, "#password": "Browser-Test-123!", "#confirm": "Browser-Test-123!" })) await fill(selector, value);
  await click("#auth-submit");
  await wait('location.pathname === "/pages/login.html" && !!document.querySelector("#auth-form")');
  pass("Customer registration");

  await login("customer");
  await fill("#profile-name", "Browser Customer Updated");
  await click("#profile-form button");
  await wait('document.querySelector("#site-toast").textContent.includes("Đã cập nhật")');
  assert.equal((await api("me()")).full_name, "Browser Customer Updated");
  await navigate("/pages/products.html", "[data-add]");
  await click("[data-favorite]");
  await wait('document.querySelector("#site-toast").textContent.includes("Đã thêm vào yêu thích")');
  await click("[data-add]");
  await wait('document.querySelector("#site-toast").textContent.includes("giỏ")');
  await navigate("/pages/wishlist.html", "[data-favorite]");
  await navigate("/pages/cart.html", "[data-inc]");
  await click("[data-inc]");
  await wait('(async()=> (await LUMIERE_API.getCart()).total_quantity === 2)()');
  await navigate("/pages/checkout.html", "#checkout-form");
  for (const [selector, value] of Object.entries({ "#recipient": "Browser Recipient", "#phone": "0901234567", "#address": "12 Test Street", "#province": "Hồ Chí Minh" })) await fill(selector, value);
  await click('#checkout-form button[type="submit"]');
  await wait('document.querySelector("#page-content").textContent.includes("Đặt hàng thành công")');
  const order = (await api('request("/orders/my")')).items[0];
  await navigate("/pages/orders.html", "#page-content .panel");
  await screenshot("customer-orders");
  assert.equal(await evaluate('fetch("/admin/orders", {credentials:"include"}).then(response => response.status)'), 403);
  await logout();
  pass("Customer login, profile, wishlist, cart quantity, COD checkout, history, role denial, logout");

  await login("staff");
  await wait('!!document.querySelector("[data-status]")');
  await click("[data-detail]");
  await wait('document.querySelector("#order-detail").textContent.includes("Browser Recipient")');
  await fill("#orders-search", "no-such-order");
  assert.equal(await evaluate('document.querySelector(".table-wrap tbody tr").hidden'), true);
  await fill("#orders-search", "");
  await fill("[data-status]", "confirmed", "change");
  // Wait for the UI refresh after commit before querying the shared SQLite connection.
  await wait('document.querySelector("[data-status]").value === "confirmed" && !document.querySelector("[data-status]").disabled');
  assert.equal((await api(`request('/staff/orders/${order.id}')`)).status, "confirmed");
  await screenshot("staff-orders");
  await navigate("/pages/staff/inventory.html", "[data-stock]");
  await evaluate('window.prompt = () => "25"');
  await click("[data-stock]");
  await wait('document.querySelector("[data-stock]").dataset.value === "25"');
  await logout();
  pass("Staff login, detail, search, order transition, stock update, logout");

  await login("admin");
  await screenshot("admin-dashboard");
  const dashboardBlocks = ["*images.unsplash.com*", "*127.0.0.1:8000*", "*localhost:8000*"];
  const dashboardSnapshot = await evaluate(`(() => {
    const root=document.querySelector('#console-body');
    return {kpis:[...root.querySelectorAll('.lm-kpi strong')].map(node=>node.textContent),
      rows:root.querySelectorAll('.data-table tbody tr').length};
  })()`);
  for (const [endpoint, source] of [["*18001/admin/reports/revenue?*", "thanh toán 30 ngày"],
    ["*18001/admin/orders?*", "đơn hàng gần nhất"], ["*18001/admin/products?*", "danh mục tồn kho"],
    ["*18001/admin/dashboard", "tổng quan"]]) {
    await cdp("Network.setBlockedURLs", {urls:[...dashboardBlocks, endpoint]});
    await navigate("/pages/admin/dashboard.html", "#console-body .form-alert");
    assert.ok(await evaluate('document.querySelector("#console-body").textContent.includes('+JSON.stringify(source)+')'));
    assert.equal(await evaluate('document.querySelectorAll("#console-body .lm-data-grid section").length'), 4);
    const remaining = await evaluate('[...document.querySelectorAll("#console-body .lm-kpi strong")].map(node=>node.textContent)');
    if (source !== "tổng quan") assert.equal(remaining[0], dashboardSnapshot.kpis[0]);
    else assert.equal(remaining[0], dashboardSnapshot.kpis[4]);
    if (source !== "đơn hàng gần nhất") assert.equal(await evaluate('document.querySelector("#console-body .data-table tbody").textContent.includes("LM")'), true);
    if (source !== "thanh toán 30 ngày") assert.equal(await evaluate('!!document.querySelector("#console-body .lm-chart")'), true);
    pass(`Dashboard ${source} endpoint offline: independent panels remain visible`);
  }
  await cdp("Network.setBlockedURLs", {urls:dashboardBlocks});
  await navigate("/pages/admin/dashboard.html", "#console-body .lm-kpi strong");
  assert.equal(await evaluate('document.querySelectorAll("#console-body .form-alert").length'), 0);
  for (const [section, selector] of [["products", "#product-search"], ["inventory", "[data-stock]"], ["orders", "[data-status]"], ["customers", "#customer-search"], ["staff", "#staff-create"], ["coupons", "#console-body .panel"], ["categories", "#lookup-rows"], ["brands", "#lookup-rows"], ["contacts", "#contact-prev"], ["analytics", "#console-body .panel"]]) {
    await navigate(`/pages/admin/${section}.html`, selector);
    assert.equal(await evaluate('!!document.querySelector("#console-body > .form-alert")'), false, section);
    pass(`Admin ${section} page and module loading`);
  }
  await navigate("/pages/admin/products.html", "#product-search");
  await evaluate('window.prompt = label => label.startsWith("Tên") ? "Updated Browser Ring" : "110000"');
  await click("[data-edit]");
  await wait('document.querySelector("[data-edit]").dataset.name === "Updated Browser Ring"');
  assert.equal((await api("product(1)")).price_vnd, "110000.00");
  await logout();
  pass("Admin product name/price update and logout");
  await login("customer");
  await navigate("/index.html", "#product-grid .product-card");
  assert.equal(await evaluate('window.__requests.filter(x=>x.url.endsWith("/auth/me")).length'), 1);
  await click("#open-cart");
  await wait('!document.querySelector("#drawer").hidden');
  await evaluate(`window.__addCount=0;const add=LUMIERE_API.addCartItem;
    LUMIERE_API.addCartItem=async function(...args){window.__addCount++;await new Promise(r=>setTimeout(r,150));return add.apply(this,args)};
    window.__cartGets=window.__requests.filter(x=>x.url.endsWith('/cart')).length;
    document.querySelector('[data-action="add"]').click();document.querySelector('[data-action="add"]').click();`);
  await wait('document.querySelector("#cart-count").textContent === "1"');
  assert.equal(await evaluate('window.__addCount'), 1);
  assert.equal(await evaluate('window.__requests.filter(x=>x.url.endsWith("/cart")).length === window.__cartGets'), true);
  await evaluate(`const button=document.querySelector('.wish-btn');window.__wasFavorite=button.classList.contains('is-active');button.click()`);
  await wait("document.querySelector('.wish-btn').classList.contains('is-active') !== window.__wasFavorite");
  pass("Homepage shares auth lookup, prevents duplicate add, reuses mutation cart, refreshes wishlist state");

  await navigate("/pages/product-detail.html?id=1", "#detail-add");
  await wait('document.querySelector("#ai-reco-status").textContent.includes("vẫn có thể")');
  await wait('!!document.querySelector("#review-form")');
  assert.equal(await evaluate('document.querySelector("#detail-add").disabled'), false);
  await click("#detail-add");
  await wait('document.querySelector("#site-toast").textContent.includes("giỏ")');
  pass("AI recommendation offline leaves product, reviews and add-to-cart usable");

  await navigate("/pages/checkout.html", "#checkout-form");
  for (const [selector, value] of Object.entries({"#recipient":"Duplicate Guard", "#phone":"0901234567", "#address":"12 Test Street", "#province":"Hồ Chí Minh"})) await fill(selector,value);
  await evaluate(`window.__orderCount=0;const create=LUMIERE_API.createOrder;
    LUMIERE_API.createOrder=async function(...args){window.__orderCount++;await new Promise(r=>setTimeout(r,150));return create.apply(this,args)};
    const form=document.querySelector('#checkout-form');form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));`);
  await wait('document.querySelector("#page-content").textContent.includes("Đặt hàng thành công")');
  assert.equal(await evaluate('window.__orderCount'),1);
  pass("Two checkout submit events produce exactly one real fixture order request");
  await logout();

  const aiBlocked=["*images.unsplash.com*", "*127.0.0.1:8000*", "*localhost:8000*"];
  await cdp("Network.setBlockedURLs", {urls:[...aiBlocked, "*18001/products?*"]});
  await navigate("/pages/products.html", "#page-content .empty-panel");
  await wait('document.querySelector("#page-content").textContent.includes("Business API")');
  await navigate("/pages/login.html", "#auth-form");
  assert.equal(await evaluate('window.__requests.some(x=>new URL(x.url,location.href).pathname === "/products")'),false);
  await login("admin");
  await wait('!!document.querySelector("#console-body .panel")');
  pass("Catalog endpoint offline reports error; login and admin dashboard avoid public catalog dependency");

  await cdp("Network.setBlockedURLs", {urls:[...aiBlocked, "*management-orders.mjs*", "*management-products.mjs*"]});
  await navigate("/pages/admin/customers.html", "#customer-search");
  await navigate("/pages/admin/orders.html", "#console-body .form-alert");
  await navigate("/pages/admin/contacts.html", "#contact-prev");
  pass("Orders/products modules blocked: customers and contacts still load; orders shows safe error");
  await cdp("Network.setBlockedURLs", {urls:aiBlocked});
  await navigate("/pages/admin/orders.html", "[data-status]");
  await evaluate(`window.__requestBeforeOutage=LUMIERE_API.request;
    LUMIERE_API.request=function(path,options){
      if(path.startsWith('/admin/orders?'))return Promise.reject(new Error('Injected list reload outage'));
      return window.__requestBeforeOutage.call(this,path,options);
    };
    const select=document.querySelector('[data-status]');window.__updatedOrderId=select.dataset.status;
    select.value='confirmed';select.dispatchEvent(new Event('change',{bubbles:true}));`);
  await wait('!!document.querySelector("#console-body .form-alert")');
  assert.equal(await evaluate('document.querySelector("[data-status]").value'), "confirmed");
  await evaluate('LUMIERE_API.request=window.__requestBeforeOutage');
  assert.equal(await evaluate('(async()=> (await LUMIERE_API.request("/orders/"+window.__updatedOrderId)).status)()'), "confirmed");
  await evaluate('document.querySelectorAll("#console-body .form-alert").forEach(node=>node.remove())');
  pass("Successful status save stays visible when the subsequent list reload fails");
  await evaluate(`window.fetch=async()=>{throw new TypeError('Injected Business API outage')};
    const outageSelect=document.querySelector('[data-status]');window.__previousStatus=outageSelect.value;
    outageSelect.value=outageSelect.value==='pending'?'confirmed':'packing';outageSelect.dispatchEvent(new Event('change',{bubbles:true}));`);
  await wait('!!document.querySelector("#console-body .form-alert")');
  assert.equal(await evaluate('document.querySelector("[data-status]").disabled'), false);
  assert.equal(await evaluate('document.querySelector("[data-status]").value === window.__previousStatus'), true);
  pass("Business API outage during status update restores control without a second failing reload");

  await cdp("Network.setBlockedURLs", {urls:[...aiBlocked, "*18001/auth/*", "*18001/products?*"]});
  await navigate("/pages/login.html", "#auth-form");
  await fill("#email","customer@example.com");await fill("#password","Browser-Test-123!");
  await click("#auth-submit");
  await wait('!document.querySelector("#form-alert").hidden && !document.querySelector("#auth-submit").disabled');
  assert.equal(await evaluate('document.querySelector("#form-alert").textContent.includes("Business API")'),true);
  pass("Business API/auth offline: login renders and submit error is visible with retry enabled");
  await cdp("Network.setBlockedURLs", {urls:aiBlocked});

  assert.deepEqual(exceptions, [], "No uncaught browser exceptions");
  await writeFile(`${evidence}/result.json`, JSON.stringify({ verified, exceptions }, null, 2));
  console.log(`${verified.length} browser checks passed; no uncaught exceptions`);
} finally {
  socket.close();
}
