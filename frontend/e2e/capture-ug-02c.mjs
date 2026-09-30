/** Story 9.3 — re-zrzuty 18/20 w wersji viewport (fullPage był zbyt wysoki). */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const shot = async (p, n) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), fullPage: false }); console.log(`📸 ${n}`); };

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
page.setDefaultTimeout(25000);

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill("anna.demo@testgen.nexio.pl");
await page.locator('input[type="password"]').first().fill("Qa-Demo-2026!Podrecznik");
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);
const projects = await page.evaluate(async () => (await (await fetch("/api/v1/projects", { credentials: "include" })).json()));
const pid = projects.projects.find((p) => p.name.includes("Sklep internetowy"))?.id ?? projects.projects[0].id;
const card = `${BASE}/projects/${pid}`;

await page.goto(card, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await page.locator("a:has-text('Wymagania'), button:has-text('Wymagania')").first().click();
await page.waitForTimeout(3000);
const frd = page.locator("a:has-text('frd'), a:has-text('FRD')").first();
if (await frd.count()) await frd.click().catch(() => {});
await page.waitForTimeout(2500);
await shot(page, "ug-02-18-wymagania");

await page.goto(card, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await page.locator("a:has-text('Glosariusz'), button:has-text('Glosariusz')").first().click();
await page.waitForTimeout(3000);
const frd2 = page.locator("a:has-text('frd'), a:has-text('FRD')").first();
if (await frd2.count()) await frd2.click().catch(() => {});
await page.waitForTimeout(2500);
await shot(page, "ug-02-20-glosariusz");

await browser.close();
console.log("✅ re-zrzuty zakończone");
