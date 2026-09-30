/** Story 9.3 — finalne poprawki v2: 21 (sekcja Porównanie z kodem) + 23 (macierz po przebudowie).
 *  Selektor dokładny a:text-is('Zobacz') — omija link „Zobacz user flows". */
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

// 21: diagram klas (pierwszy dokładny „Zobacz") + Porównanie z kodem
await page.goto(`${card}/uml`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.locator("a:has-text('Zobacz')").filter({ hasNotText: /user flows/i }).first().click();
await page.waitForTimeout(2500);
console.log("URL diagramu:", page.url());
const cmp = page.getByRole("button", { name: /Porównaj z kodem/i }).first();
console.log("przycisk Porównaj z kodem:", await cmp.count());
if (await cmp.count()) {
  await cmp.click();
  await page.waitForTimeout(5000);
}
const sec = page.locator("h2:has-text('Porównanie z kodem'), h3:has-text('Porównanie z kodem'), :text('Porównanie z kodem')").first();
console.log("sekcja Porównanie z kodem:", await sec.count());
if (await sec.count()) await sec.scrollIntoViewIfNeeded().catch(() => {});
await page.waitForTimeout(1000);
await shot(page, "ug-02-21-diagram-klas");

// 23: macierz śledzenia po przebudowie
await page.goto(card, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await page.locator("a:has-text('Macierz śledzenia'), button:has-text('Macierz śledzenia')").first().click();
await page.waitForTimeout(2500);
const rebuild = page.getByRole("button", { name: /Przebuduj macierz/ }).first();
console.log("przycisk Przebuduj macierz:", await rebuild.count());
if (await rebuild.count()) {
  await rebuild.click();
  await page.waitForTimeout(10000);
}
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(2500);
const rows = await page.locator("table tbody tr, mat-row").count().catch(() => 0);
console.log("wierszy macierzy:", rows);
await shot(page, "ug-02-23-macierz-sledzenia");

await browser.close();
console.log("✅ finalne poprawki v2 zakończone");
