// Read-only guest checks. Never signs in, creates orders, or alters original accounts.
const assert = require('node:assert/strict');
const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch({executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    await page.goto('http://127.0.0.1:18080/pages/products.html', {timeout: 60000});
    await page.waitForFunction(() => window.LUMIERE_PRODUCTS?.length === 500, {timeout: 60000});
    await page.locator('#catalog-results .catalog-card').first().waitFor();
    const mapped = await page.evaluate(() => window.LUMIERE_PRODUCTS.every(p =>
      p.sku.startsWith('SP') && p.image === window.LUMIERE_PRODUCT_IMAGES[p.sku] && !p.imageDemo));
    assert.equal(mapped, true);
    const image = page.locator('#catalog-results .catalog-card img').first();
    await image.scrollIntoViewIfNeeded();
    await image.evaluate(img => img.decode());
    assert.ok(await image.evaluate(img => img.naturalWidth > 0));
    await page.locator('#catalog-results .catalog-card a').first().click();
    await page.locator('.detail-photo').waitFor();
    await page.locator('.detail-photo').evaluate(img => img.decode());
    const detail = await page.locator('.detail-photo').evaluate(img => ({loaded:img.naturalWidth>0, path:new URL(img.src).pathname}));
    assert.ok(detail.loaded && detail.path.startsWith('/assets/images/products/SP'));
    // Resolve a high SKU too: catches accidental rendering of only the first API page.
    await page.goto('http://127.0.0.1:18080/pages/product-detail.html?id=500');
    await page.locator('.detail-photo').waitFor();
    await page.locator('.detail-photo').evaluate(img => img.decode());
    assert.ok(await page.locator('.detail-photo').evaluate(img => img.naturalWidth>0));
    console.log(JSON.stringify({successful:true,browser:'actual installed Chrome',catalog_products:500,
      all_catalog_sku_images_mapped:true,catalog_first_image_decoded:true,detail_images_decoded:2,
      authentication_tested:false,private_rows_accessed:false,writes_performed:false}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error.message); process.exitCode=1;});
