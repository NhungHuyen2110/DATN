const path = require('path');
module.exports = {
  testDir: __dirname,
  testMatch: 'isolated.spec.cjs',
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  outputDir: process.env.LUMIERE_BROWSER_ARTIFACT_DIR,
  reporter: [['list'], ['json', { outputFile: process.env.LUMIERE_BROWSER_JSON_REPORT }]],
  use: {
    baseURL: process.env.LUMIERE_E2E_BASE_URL,
    browserName: 'chromium',
    launchOptions: { executablePath: process.env.LUMIERE_E2E_BROWSER_PATH },
    screenshot: 'only-on-failure', trace: 'retain-on-failure'
  }
};
