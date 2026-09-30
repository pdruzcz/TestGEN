/**
 * Story 9.3 — dokładka do capture-ug-02.mjs: brakujące zrzuty list źródeł (08-10)
 * oraz widoków analizy dokumentacji (18-20). Selektory: przyciski, nie linki.
 * Uruchomienie (frontend/): node e2e/capture-ug-02b.mjs
 */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const EMAIL = "anna.demo@testgen.nexio.pl";
const PASSWORD = "Qa-Demo-2026!Podrecznik";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");

const shot = async (page, name, opts = {}) => {
  await page.screenshot({ path: join(IMG_DIR, `${name}.png`), fullPage: false, ...opts });
  console.log(`📸 ${name}`);
};
const step = async (label, fn) => {
  try { await fn(); } catch (e) { console.log(`⚠️  ${label}: ${String(e).split("\n")[0].slice(0, 140)}`); }
};

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
page.setDefaultTimeout(25000);

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL);
await page.locator('input[type="password"]').first().fill(PASSWORD);
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);
const projects = await page.evaluate(async () => (await (await fetch("/api/v1/projects", { credentials: "include" })).json()));
const pid = projects.projects.find((p) => p.name.includes("Sklep internetowy"))?.id ?? projects.projects[0].id;
const card = `${BASE}/projects/${pid}`;
console.log("PID:", pid);

// ============ LISTY ŹRÓDEŁ (dane już wgrane przez capture-ug-02) ============
await step("lista dokumentów", async () => {
  await page.goto(`${card}/documents`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await shot(page, "ug-02-08-dokumenty", { fullPage: true });
});
await step("lista UML", async () => {
  await page.goto(`${card}/uml`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await shot(page, "ug-02-09-diagramy-uml", { fullPage: true });
});
await step("lista GUI", async () => {
  await page.goto(`${card}/gui`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await shot(page, "ug-02-10-zrzuty-gui", { fullPage: true });
});

// ============ WIDOKI ANALIZY DOKUMENTACJI (przez kafelki karty projektu) ============
const kafelek = (txt) => page.locator(`a:has-text('${txt}'), button:has-text('${txt}')`).first();

await step("wymagania (z retry na trwającą analizę)", async () => {
  let ok = false;
  for (let i = 0; i < 20 && !ok; i++) {
    await page.goto(card, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    await kafelek("Wymagania").click({ timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(3500);
    // jeśli lista dokumentów do wyboru — wejdź w FRD (najbogatszy w wymagania)
    const frd = page.locator("a:has-text('frd'), a:has-text('FRD')").first();
    if (await frd.count()) await frd.click().catch(() => {});
    await page.waitForTimeout(2500);
    const has = await page.locator("text=/Znaleziono:|Funkcjonalne|Niefunkcjonalne/").count().catch(() => 0);
    console.log(`  próba ${i + 1}: treść wymagań widoczna = ${has}`);
    ok = has > 0;
  }
  await shot(page, "ug-02-18-wymagania", { fullPage: true });
});
await step("niespójności", async () => {
  await page.goto(card, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await kafelek("Niespójności").click();
  await page.waitForTimeout(3000);
  await shot(page, "ug-02-19-niespojnosci", { fullPage: true });
});
await step("glosariusz", async () => {
  await page.goto(card, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await kafelek("Glosariusz").click();
  await page.waitForTimeout(3000);
  await shot(page, "ug-02-20-glosariusz", { fullPage: true });
});

await browser.close();
console.log("✅ capture-ug-02b zakończony");
