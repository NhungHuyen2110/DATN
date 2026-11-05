"use strict";

const { test, expect } = require("@playwright/test");

const baseURL = process.env.LUMIERE_E2E_BASE_URL || "http://127.0.0.1:8001";
const localHost = ["localhost", "127.0.0.1"].includes(new URL(baseURL).hostname);
const isolatedDatabase = process.env.LUMIERE_E2E_DB_KIND === "isolated";
const allowWrites = process.env.LUMIERE_E2E_ALLOW_WRITE === "1";
const canReadLocal = localHost && isolatedDatabase;
const canWriteLocal = canReadLocal && allowWrites;
const account = role => ({
  email: process.env[`LUMIERE_E2E_${role.toUpperCase()}_EMAIL`],
  password: process.env[`LUMIERE_E2E_${role.toUpperCase()}_PASSWORD`]
});

async function login(page, credentials) {
  await page.goto("/pages/login.html");
  await page.getByLabel("Email").fill(credentials.email);
  await page.locator("#password").fill(credentials.password);
  await page.getByRole("button", { name: "ĐĂNG NHẬP" }).click();
}

test.describe("Guest shopping", () => {
  test.skip(!canReadLocal, "BLOCKED: cần Business API trên localhost với database test độc lập.");

  test("catalog remains available when AI chat and recommendations are offline; protected pages redirect", async ({ page }) => {
    await page.route("**/recommendations/v2**", route => route.abort());
    await page.route("**/chat", route => route.abort());
    await page.goto("/pages/products.html");
    await expect(page.locator("#catalog-results .catalog-card").first()).toBeVisible();
    await expect(page.locator("#result-count")).toContainText("sản phẩm");

    await page.goto("/pages/admin/dashboard.html");
    await expect(page).toHaveURL(/\/pages\/login\.html$/);
  });
});

test.describe("Customer account and COD", () => {
  const credentials = account("customer");
  test.skip(!canWriteLocal,
    "BLOCKED: cần cho phép ghi trên database test độc lập.");

  test("registers a local test customer and logs in", async ({ page }) => {
    const email = `lumiere-e2e-${Date.now()}@example.test`;
    const password = "E2E-Test-Password-123!";
    await page.goto("/pages/register.html");
    await page.getByLabel("Họ tên").fill("Khách kiểm thử LUMIÈRE");
    await page.getByLabel("Số điện thoại").fill("0901234567");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
    await page.getByLabel("Nhập lại mật khẩu").fill(password);
    await page.getByRole("button", { name: "ĐĂNG KÝ" }).click();
    await expect(page).toHaveURL(/\/pages\/login\.html$/);
    await login(page, { email, password });
    await expect(page).toHaveURL(/\/pages\/account\.html$/);
    await page.getByRole("button", { name: "ĐĂNG XUẤT" }).click();
    await expect(page).toHaveURL(/\/pages\/login\.html$/);
  });

  test("login, catalog, wishlist, cart, COD checkout, order history, role denial and logout", async ({ page }) => {
    test.skip(!credentials.email || !credentials.password,
      "BLOCKED: thiếu tài khoản Customer thử nghiệm.");
    await login(page, credentials);
    await expect(page).toHaveURL(/\/pages\/account\.html$/);

    await page.goto("/pages/products.html");
    await expect(page.locator("#catalog-results .catalog-card").first()).toBeVisible();
    const firstCard = page.locator("#catalog-results .catalog-card")
      .filter({ has: page.locator("[data-add]:not([disabled])") }).first();
    await firstCard.locator("[data-favorite]").click();
    await firstCard.locator("[data-add]").click();

    await page.goto("/pages/cart.html");
    await expect(page.locator("#page-content")).toContainText("Giỏ hàng");
    await page.goto("/pages/checkout.html");
    await page.getByLabel("Họ và tên").fill("Khách kiểm thử LUMIÈRE");
    await page.getByLabel("Số điện thoại").fill("0901234567");
    await page.getByLabel("Địa chỉ nhận hàng").fill("12 Đường Kiểm Thử");
    await page.getByLabel("Tỉnh / thành phố").fill("TP. Hồ Chí Minh");
    await page.getByRole("button", { name: "ĐẶT HÀNG COD" }).click();
    await expect(page.locator("#page-content")).toContainText("Đặt hàng thành công");

    await page.goto("/pages/orders.html");
    await expect(page.locator("#page-content")).toContainText("Đơn hàng của tôi");
    await page.goto("/pages/wishlist.html");
    await expect(page.locator("#page-content")).toContainText("Yêu thích");
    await page.goto("/pages/admin/dashboard.html");
    await expect(page).toHaveURL(/\/pages\/products\.html$/);

    await page.goto("/pages/account.html");
    await page.getByRole("button", { name: "ĐĂNG XUẤT" }).click();
    await expect(page).toHaveURL(/\/pages\/login\.html$/);
  });
});

for (const role of ["admin", "staff"]) {
  test.describe(`${role} operations`, () => {
    const credentials = account(role);
    test.skip(!canReadLocal || !credentials.email || !credentials.password,
      `BLOCKED: cần tài khoản ${role} thử nghiệm trên database test độc lập.`);

    test("role navigation and operational pages load from Business API", async ({ page }) => {
      await login(page, credentials);
      await expect(page).toHaveURL(role === "admin"
        ? /\/pages\/admin\/dashboard\.html$/
        : /\/pages\/staff\/orders\.html$/);

      const pages = role === "admin"
        ? ["dashboard", "products", "orders", "customers", "staff", "coupons", "inventory", "categories", "brands", "analytics"]
        : ["orders", "inventory"];
      for (const name of pages) {
        await page.goto(`/pages/${role === "admin" ? "admin/" : "staff/"}${name}.html`);
        await expect(page.locator(".backend-console")).toBeVisible();
        await expect(page.locator(".form-alert")).toHaveCount(0);
      }

      const denied = role === "admin" ? "/pages/staff/orders.html" : "/pages/admin/dashboard.html";
      await page.goto(denied);
      await expect(page).toHaveURL(role === "admin"
        ? /\/pages\/admin\/dashboard\.html$/
        : /\/pages\/staff\/orders\.html$/);
    });

    test("updates a fixture order status when an isolated order is configured", async ({ page }) => {
      const orderId = process.env.LUMIERE_E2E_ORDER_ID;
      const nextStatus = process.env.LUMIERE_E2E_ORDER_STATUS;
      test.skip(!canWriteLocal || !orderId || !nextStatus,
        "BLOCKED: thiếu fixture đơn hàng và trạng thái chuyển hợp lệ trên database test.");
      await login(page, credentials);
      await page.goto(`/pages/${role === "admin" ? "admin" : "staff"}/orders.html`);
      const status = page.locator(`select[data-status="${orderId}"]`);
      await expect(status).toBeVisible();
      await status.selectOption(nextStatus);
      await expect(page.locator(`select[data-status="${orderId}"]`)).toHaveValue(nextStatus);
    });

    test("updates a fixture stock count without changing it when configured", async ({ page }) => {
      const productId = process.env.LUMIERE_E2E_STOCK_PRODUCT_ID;
      test.skip(!canWriteLocal || !productId,
        "BLOCKED: thiếu ProductID fixture trên database test độc lập.");
      await login(page, credentials);
      await page.goto(`/pages/${role === "admin" ? "admin" : "staff"}/inventory.html`);
      const update = page.locator(`button[data-stock="${productId}"]`);
      await expect(update).toBeVisible();
      const currentStock = await update.getAttribute("data-value");
      page.once("dialog", dialog => dialog.accept(currentStock));
      await update.click();
      await expect(page.locator(`button[data-stock="${productId}"]`)).toHaveAttribute("data-value", currentStock);
    });

    test("confirms collection for a delivered COD fixture when configured", async ({ page }) => {
      const orderId = process.env.LUMIERE_E2E_COD_ORDER_ID;
      test.skip(!canWriteLocal || !orderId,
        "BLOCKED: cần đơn COD delivered/unpaid fixture trên database test độc lập.");
      await login(page, credentials);
      await page.goto(`/pages/${role === "admin" ? "admin" : "staff"}/orders.html`);
      const confirm = page.locator(`button[data-cod="${orderId}"]`);
      await expect(confirm).toBeEnabled();
      page.once("dialog", dialog => dialog.accept("E2E-COLLECTION-001"));
      await confirm.click();
      await expect(page.locator(`button[data-cod="${orderId}"]`)).toBeDisabled();
    });
  });
}
