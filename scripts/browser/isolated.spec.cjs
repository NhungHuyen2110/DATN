const { test, expect } = require('@playwright/test');
const apiPrefix = process.env.LUMIERE_E2E_API_PREFIX || '';
if (!['', '/api'].includes(apiPrefix)) throw new Error('Unexpected isolated API prefix');
const apiPath = path => apiPrefix + path;
const aiBase = apiPrefix ? new URL('/ai', process.env.LUMIERE_E2E_BASE_URL).href : 'http://127.0.0.1:18000';
const grafanaBase = apiPrefix ? 'http://localhost:18080/grafana' : 'http://127.0.0.1:13000';
// Existing API adapter supports runtime configuration. Keep source HTML/JS intact.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(({prefix, ai}) => {
    window.LUMIERE_API_BASE = window.location.origin + prefix;
    window.LUMIERE_AI_BASE = ai;
  }, {prefix: apiPrefix, ai: aiBase});
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (['localhost', '127.0.0.1'].includes(url.hostname)) return route.continue();
    return route.abort();
  });
});
require('../../frontend/tests/e2e/lumiere.spec.js');

test('existing password reset preserves single-use token and invalidates old sessions', async ({page, request}) => {
  const email = process.env.LUMIERE_E2E_RESET_EMAIL;
  const oldPassword = process.env.LUMIERE_E2E_RESET_OLD_PASSWORD;
  const token = process.env.LUMIERE_E2E_RESET_TOKEN;
  test.skip(!email || !token, 'Requires a synthetic single-use reset fixture');
  const oldLogin = await request.post(apiPath('/auth/login'), {data: {email, password: oldPassword}});
  expect(oldLogin.ok()).toBeTruthy();
  await page.goto('/pages/forgot-password.html');
  await page.getByLabel('Email').fill(process.env.LUMIERE_E2E_CUSTOMER_EMAIL);
  const forgot = page.waitForResponse(result => new URL(result.url()).pathname.endsWith('/auth/forgot-password'));
  await page.getByRole('button', {name: 'GỬI YÊU CẦU KHÔI PHỤC'}).click();
  const forgotResponse = await forgot;
  expect(forgotResponse.ok()).toBeTruthy();
  const forgotPayload = await forgotResponse.json();
  expect(forgotPayload.token).toBeUndefined();
  expect(forgotPayload.reset_url).toBeUndefined();
  await page.goto('/pages/reset-password.html?token=' + encodeURIComponent(token));
  const password = 'Synthetic-New-Password-2026!';
  await page.getByLabel('Mật khẩu mới', {exact: true}).fill(password);
  await page.getByLabel('Nhập lại mật khẩu').fill(password);
  await page.getByRole('button', {name: 'Đổi mật khẩu'}).click();
  await expect(page.locator('#feedback')).toContainText('Đổi mật khẩu thành công');
  await expect(page).not.toHaveURL(/token=/);
  expect((await request.get(apiPath('/auth/me'))).status()).toBe(401);
  expect((await request.post(apiPath('/auth/reset-password'), {data: {token, new_password: password}})).status()).toBe(400);
  expect((await request.post(apiPath('/auth/login'), {data: {email, password: oldPassword}})).status()).toBe(401);
  expect((await request.post(apiPath('/auth/login'), {data: {email, password}})).ok()).toBeTruthy();
});

test('diagnostics page redirects guests before showing the form', async ({ page }) => {
  await page.goto('/pages/admin/ai-diagnostics.html');
  await expect(page).toHaveURL(/\/pages\/login\.html$/);
});

for (const role of ['customer', 'staff']) {
  test(`diagnostics rejects ${role} at UI and backend`, async ({ page }) => {
    const login = await page.request.post(apiPath('/auth/login'), { data: {
      email: process.env[`LUMIERE_E2E_${role.toUpperCase()}_EMAIL`],
      password: process.env[`LUMIERE_E2E_${role.toUpperCase()}_PASSWORD`]
    }});
    expect(login.ok()).toBeTruthy();
    const denied = await page.request.post(apiPath('/admin/ai/retrieval-diagnostics'), { data: { query: 'nhẫn' }});
    expect(denied.status()).toBe(403);
    await page.goto('/pages/admin/ai-diagnostics.html');
    await expect(page).toHaveURL(role === 'staff' ? /\/pages\/staff\/orders\.html$/ : /\/pages\/products\.html$/);
  });
}

test('Admin sees verified retrieval diagnostics and opt-in graph feature scores', async ({ page }) => {
  // Includes login, page boot and two separate diagnostic requests. Keep the
  // API/proxy per-request deadlines unchanged; this is a whole-scenario budget.
  test.setTimeout(90000);
  test.skip(process.env.LUMIERE_BROWSER_WITH_AI !== '1', 'Requires isolated source AI API');
  const login = await page.request.post(apiPath('/auth/login'), { data: {
    email: process.env.LUMIERE_E2E_ADMIN_EMAIL, password: process.env.LUMIERE_E2E_ADMIN_PASSWORD
  }});
  expect(login.ok()).toBeTruthy();
  await page.goto('/pages/admin/ai-diagnostics.html');
  await expect(page.locator('#diagnostics-form')).toBeVisible();
  async function diagnose() {
    const response = page.waitForResponse(result => new URL(result.url()).pathname === apiPath('/admin/ai/retrieval-diagnostics'));
    await page.getByRole('button', { name: 'CHẠY CHẨN ĐOÁN' }).click();
    const result = await response;
    expect(result.ok()).toBeTruthy();
    return result.json();
  }
  const result = await diagnose();
  const semantic = process.env.LUMIERE_BROWSER_WITH_SEMANTIC === '1';
  expect(result.status).toBe(semantic ? 'ok' : 'degraded');
  expect(result.returned_k).toBe(3);
  expect(result.products[0].score_type).toBe('rrf');
  expect(result.products[0].score).toBeGreaterThan(0);
  if (semantic) {
    expect(result.products[0].retrieval_sources).toEqual(expect.arrayContaining(['lexical', 'dense', 'graph']));
    expect(result.products[0].graph_paths.length).toBeGreaterThan(0);
  } else {
    expect(result.products[0].retrieval_sources).toEqual(['lexical']);
  }
  await expect(page.locator('#diagnostics-output')).toBeVisible();
  await page.locator('#rerank').check();
  const reranked = await diagnose();
  expect(reranked.products[0].score_type).toBe('normalized_rrf_verified_graph_v1');
  if (semantic) expect(reranked.products[0].rerank_features.verified_graph).toBeGreaterThan(0);
  else expect(reranked.products[0].rerank_features.verified_graph).toBe(0);
});

test('public recommendations ignore supplied customer identity and render compatible cards', async ({ page }) => {
  test.setTimeout(90000); // Two API calls plus a page load and its recommendation request.
  test.skip(process.env.LUMIERE_BROWSER_WITH_AI !== '1', 'Requires isolated source AI API');
  const read = async customer => {
    const response = await page.request.get(aiBase + '/recommendations/v2', {
      params: {customer_id: customer, product_id: 1, number: 4}
    });
    expect(response.ok()).toBeTruthy();
    return response.json();
  };
  const guest = await read('GUEST');
  const other = await read('OTHER_CUSTOMER');
  expect(guest.personalized).toBe(false);
  expect(other.data).toEqual(guest.data);
  expect(guest.number).toBeGreaterThan(0);
  expect(guest.data.every(item => item.ProductID !== 1 && item.Stock > 0)).toBeTruthy();
  await page.goto('/pages/product-detail.html?id=1');
  await expect(page.locator('#ai-reco-grid .catalog-card').first()).toBeVisible({timeout: 15000});
});

test('Grafana renders provisioned dashboard backed by actual Prometheus scrapes', async ({ page }) => {
  test.skip(process.env.LUMIERE_BROWSER_WITH_MONITORING !== '1', 'Requires isolated native monitoring lab');
  test.setTimeout(90000);
  const login = await page.request.post(grafanaBase + '/login', {data: {
    user: 'admin', password: process.env.LUMIERE_GRAFANA_TEST_PASSWORD
  }});
  expect(login.ok()).toBeTruthy();
  await page.setViewportSize({width: 1600, height: 1100});
  await page.goto(grafanaBase + '/d/lumiere-runtime?from=now-5m&to=now&refresh=5s&kiosk');
  await expect(page.getByText('Requests / second', {exact: true}).first()).toBeVisible({timeout: 30000});
  await expect(page.getByText('Scrape target health', {exact: true}).first()).toBeVisible({timeout: 30000});
  // Wait for actual query responses, not an arbitrary screenshot of empty panels.
  await expect(page.locator('canvas').first()).toBeVisible({timeout: 30000});
  await page.screenshot({path: process.env.LUMIERE_GRAFANA_SCREENSHOT, fullPage: true});
});
