/** Story 9.4 — re-zrzuty 12/13 w wersji viewport (fullPage przekroczył limit 500 KB haka). */
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

await page.goto(`${BASE}/projects/${pid}/gap-analysis`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await shot(page, "ug-03-12-luki-funkcjonalne");

await page.goto(`${BASE}/projects/${pid}/recommendations`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await shot(page, "ug-03-13-rekomendacje");

await browser.close();
console.log("✅ re-zrzuty 12/13 zakończone");
