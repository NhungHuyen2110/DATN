"use strict";

const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 10000 },
  reporter: "list",
  outputDir: "test-results/e2e",
  use: {
    baseURL: process.env.LUMIERE_E2E_BASE_URL || "http://127.0.0.1:8001",
    browserName: "chromium",
    screenshot: "only-on-failure",
    trace: "retain-on-failure"
  }
});
