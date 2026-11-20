import assert from "node:assert/strict";
import test from "node:test";
import { createManagementConsole } from "../../assets/js/pages/management-console.mjs";

// API fixtures stay in tests; exercise the real dashboard renderer and error markup.
async function render(t, failedSource) {
  const previousWindow = globalThis.window;
  const previousDocument = globalThis.document;
  const summary = { total_orders: 37, total_products: 12, out_of_stock_products: 2,
    confirmed_payment_amount_vnd: "500000", reconciliation_order_count: 3,
    reconciliation_order_value_vnd: "900000", orders_by_status: { pending: 11 },
    reconciliation_reasons: [{ reason: "Needs review", order_count: 3 }] };
  const orders = { items: [{ code: "ORDER-REGRESSION", status: "pending", payment_status: "unpaid", total_vnd: "250000" }] };
  const products = { items: [{ id: 7, name: "LOW-STOCK-REGRESSION", stock: 3 }], total: 1 };
  const revenue = { confirmed_payment_amount_vnd: "123450", confirmed_payment_order_count: 4,
    items: [{ period_start: "2026-11-01", confirmed_payment_amount_vnd: "123450" }] };
  const source = (name, data) => async () => {
    if (failedSource === name) throw new Error(`${name} unavailable <script>alert(1)</script>`);
    return data;
  };
  globalThis.window = { LUMIERE_API: {
    dashboard: source("summary", summary), adminOrders: source("orders", orders),
    adminProducts: source("products", products), revenue: source("revenue", revenue)
  } };
  globalThis.document = { body: { dataset: { root: "../../" } } };
  t.after(() => {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
    if (previousDocument === undefined) delete globalThis.document;
    else globalThis.document = previousDocument;
  });
  const target = { innerHTML: "", textContent: "" };
  const mount = { innerHTML: "", querySelector: () => target };
  await createManagementConsole()({ mount, section: "dashboard", role: "admin" });
  return target.innerHTML;
}

test("dashboard renders all successful sources without an error", async t => {
  const html = await render(t);
  assert.match(html, /<strong>37<\/strong>/);
  assert.match(html, /ORDER-REGRESSION/);
  assert.match(html, /LOW-STOCK-REGRESSION/);
  assert.match(html, /123\.450 ₫/);
  assert.doesNotMatch(html, /role="alert"/);
});

for (const failed of ["revenue", "orders", "products", "summary"]) {
  test(`${failed} failure leaves independent dashboard sources visible`, async t => {
    const html = await render(t, failed);
    assert.match(html, new RegExp(`${failed} unavailable &lt;script&gt;`));
    assert.match(html, /role="alert"/);
    assert.doesNotMatch(html, /<script>|undefined|NaN/);
    if (failed !== "summary") {
      assert.match(html, /<strong>37<\/strong>/);
      assert.match(html, /11 đơn chờ xác nhận/);
      assert.match(html, /Needs review: 3 đơn/);
    } else {
      assert.doesNotMatch(html, /<strong>37<\/strong>|Chưa phát hiện trường hợp cần đối soát/);
    }
    if (failed !== "orders") assert.match(html, /ORDER-REGRESSION/);
    else assert.doesNotMatch(html, /ORDER-REGRESSION|Chưa có đơn<\/td>/);
    if (failed !== "products") assert.match(html, /LOW-STOCK-REGRESSION/);
    else assert.doesNotMatch(html, /LOW-STOCK-REGRESSION|Chưa có sản phẩm tồn kho thấp/);
    if (failed !== "revenue") assert.match(html, /123\.450 ₫/);
    else assert.doesNotMatch(html, /123\.450 ₫|class="lm-chart"/);
  });
}
