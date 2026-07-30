import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
  webServer: {
    // E2E validates the same optimized artifact shipped to production.
    // Next does not copy static/public assets into the standalone directory.
    // Mirror the production image before testing so CSS, hydration and the
    // accessibility tree are tested as users receive them.
    command:
      "npm run build && cp -R public .next/standalone/ && mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/ && HOSTNAME=127.0.0.1 PORT=3000 node .next/standalone/server.js",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    // The optimized production build is deliberately used for E2E. It can
    // exceed two minutes on a one-CPU CI runner, so retain a bounded five
    // minute startup window rather than reporting a false application failure.
    timeout: 300_000,
    env: {
      ...process.env,
      AUTH_BYPASS: "true",
      NEXT_PUBLIC_AUTH_BYPASS: "true",
      NEXT_PUBLIC_CHAT_V2: "true",
    },
  },
});
