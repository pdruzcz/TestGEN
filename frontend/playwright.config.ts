import { defineConfig, devices } from "@playwright/test";

/**
 * Story 6.13 — konfiguracja testów E2E (Playwright).
 *
 * Testy działają w pełni na zamockowanym API (page.route) — backend nie jest
 * wymagany. Uruchamiany jest wyłącznie dev-server Angulara (npm start).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: {
    // Angular Material animacje + lazy-loaded routes — 10 s wystarcza
    timeout: 10_000,
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: "http://localhost:4200",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "pl-PL",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: {
    command: "npm start",
    url: "http://localhost:4200",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
