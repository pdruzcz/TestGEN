/** Story 9.4 — dokładka: zrzut 10 (szczegóły podatności z rekomendacją i diffem). */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const shot = async (p, n, o = {}) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), fullPage: false, ...o }); console.log(`📸 ${n}`); };

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

await page.goto(`${BASE}/projects/${pid}/security`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);

// raport zagregowany zasila listę znalezisk z przyciskiem „Pokaż rekomendację"
const gen = page.getByRole("button", { name: /Generuj raport zagregowany/ }).first();
if (await gen.count()) {
  await gen.click();
  await page.waitForTimeout(8000);
}
const show = page.getByRole("button", { name: /Pokaż rekomendację/ }).first();
console.log("przycisk Pokaż rekomendację:", await show.count());
if (await show.count()) {
  await show.click();
  await page.waitForTimeout(2500);
  const genRec = page.getByRole("button", { name: /Generuj rekomendację/ }).first();
  console.log("przycisk Generuj rekomendację:", await genRec.count());
  if (await genRec.count()) {
    await genRec.click();
    await page.waitForTimeout(8000);
  }
}
const det = page.locator("text=Opis problemu").first();
console.log("sekcja Opis problemu:", await det.count());
if (await det.count()) await det.scrollIntoViewIfNeeded().catch(() => {});
await page.waitForTimeout(800);
await shot(page, "ug-03-10-rekomendacja-podatnosci", { fullPage: true });

await browser.close();
console.log("✅ dokładka 9.4 zakończona");
