/** Story 9.2 — etap 5 (fix): zakładka Pokrycie, pasek dostępności + kontrast, mobile. */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const EMAIL = "anna.demo@testgen.nexio.pl";
const PASSWORD = "Qa-Demo-2026!Podrecznik";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const shot = async (p, n, o = {}) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), ...o }); console.log("📸 " + n); };
const login = async (p) => {
  await p.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await p.locator('input[type="email"], input[name="email"]').first().fill(EMAIL);
  await p.locator('input[type="password"]').first().fill(PASSWORD);
  await p.keyboard.press("Enter");
  await p.waitForURL(/dashboard|projects/);
  await p.waitForTimeout(1200);
};

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
await login(page);
const pid = (await page.evaluate(async () => (await (await fetch("/api/v1/projects", { credentials: "include" })).json()))).projects[0].id;

// zakładka Pokrycie w wynikach
await page.goto(`${BASE}/projects/${pid}/results`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.locator("a:has-text('Pokrycie'), [role=tab]:has-text('Pokrycie')").first().click().catch(async () => {});
await page.waitForTimeout(1500);
await shot(page, "ug-01-14-pokrycie");

// pasek dostępności — przycisk accessibility_new w sidebarze
await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
await page.locator('button:has-text("accessibility_new"), button [maticon]:has-text("accessibility"), button:has(mat-icon):has-text("accessibility_new")').first()
  .or(page.getByRole("button", { name: /dostępno/i })).first().click().catch(() => {});
await page.waitForTimeout(600);
await shot(page, "ug-01-23-pasek-dostepnosci");
// przełącznik kontrastu — najczęściej pierwszy/typu contrast w rozwiniętym pasku
const hcBtns = await page.locator("button:visible").allTextContents().catch(() => []);
console.log("BTNS po rozwinięciu:", JSON.stringify(hcBtns.filter(t => t.trim()).map(t => t.trim().slice(0, 26)).slice(-8)));
const hc = page.getByRole("button", { name: /wysoki kontrast|high contrast/i }).first();
if (await hc.count()) {
  await hc.click();
  await page.waitForTimeout(600);
  await shot(page, "ug-01-24-wysoki-kontrast");
  await hc.click();
}

// mobile
const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "pl-PL" });
const mp = await mctx.newPage();
await login(mp);
await shot(mp, "ug-01-27-mobilny-dashboard");
await mctx.close();

await browser.close();
console.log("✅ etap 5 zakończony");
