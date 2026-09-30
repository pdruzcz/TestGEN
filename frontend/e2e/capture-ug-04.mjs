/**
 * Story 9.5 — zrzuty do podręcznika cz. 4 (integracje + ustawienia).
 * MFA: klikamy tylko "Włącz MFA" (ekran QR bez potwierdzenia — MFA nie zostaje włączone).
 * Uruchomienie (frontend/): node e2e/capture-ug-04.mjs
 */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const shot = async (p, n, o = {}) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), fullPage: false, ...o }); console.log(`📸 ${n}`); };
const step = async (l, fn) => { try { await fn(); } catch (e) { console.log(`⚠️  ${l}: ${String(e).split("\n")[0].slice(0, 140)}`); } };

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
console.log("PID:", pid);

// ====== INTEGRACJE ======
await step("integracje: Jira (zrzut 01)", async () => {
  await page.goto(`${BASE}/projects/${pid}/integrations`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const btn = page.getByRole("button", { name: /^Jira$/ }).first();
  if (await btn.count()) await btn.click();
  await page.waitForTimeout(800);
  // wypełnij przykładowymi wartościami (bez zapisu/testu połączenia)
  const fill = async (label, val) => {
    const f = page.locator(`mat-form-field:has-text('${label}') input, mat-form-field:has-text('${label}') textarea`).first();
    if (await f.count()) await f.fill(val).catch(() => {});
  };
  await fill("URL instancji Jira", "https://twoj-projekt.atlassian.net");
  await fill("Email", "ty@firma.pl");
  await fill("API Token", "ATATT3x…");
  await fill("Klucz projektu", "PROJ");
  await page.waitForTimeout(500);
  await shot(page, "ug-04-01-integracje-jira");
});
await step("integracje: Azure DevOps (zrzut 02)", async () => {
  const ado = page.getByRole("button", { name: /Azure DevOps/i }).first();
  if (await ado.count()) await ado.click();
  await page.waitForTimeout(800);
  const fill = async (label, val) => {
    const f = page.locator(`mat-form-field:has-text('${label}') input`).first();
    if (await f.count()) await f.fill(val).catch(() => {});
  };
  await fill("Organizacja", "my-org");
  await fill("Projekt", "MyProject");
  await fill("Personal Access Token", "xxxxxxxx…");
  await page.waitForTimeout(500);
  await shot(page, "ug-04-02-integracje-ado");
});
await step("integracje: synchronizacja + historia (zrzut 03)", async () => {
  const sec = page.locator("text=Synchronizacja").first();
  if (await sec.count()) await sec.scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(800);
  await shot(page, "ug-04-03-integracje-sync");
});

// ====== USTAWIENIA ======
await step("profil (zrzut 04)", async () => {
  await page.goto(`${BASE}/settings/profile`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot(page, "ug-04-04-ustawienia-profil");
});
await step("MFA — ekran QR bez potwierdzania (zrzut 05)", async () => {
  await page.goto(`${BASE}/settings/mfa`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const start = page.getByRole("button", { name: /Włącz MFA/ }).first();
  if (await start.count()) {
    await start.click();
    await page.waitForTimeout(2500); // QR generowany po stronie klienta
  }
  await shot(page, "ug-04-05-ustawienia-mfa");
  // bez "Weryfikuj i włącz" — MFA pozostaje wyłączone
});
await step("powiadomienia (zrzut 06)", async () => {
  await page.goto(`${BASE}/settings/profile`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const sec = page.locator("#powiadomienia").first();
  if (await sec.count()) await sec.scrollIntoViewIfNeeded().catch(() => {});
  else await page.locator("text=Powiadomienia o limitach").first().scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(600);
  await shot(page, "ug-04-06-ustawienia-powiadomienia");
});
await step("użytkownicy firmy (zrzut 07)", async () => {
  await page.goto(`${BASE}/settings/users`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot(page, "ug-04-07-uzytkownicy");
});

await browser.close();
console.log("✅ capture-ug-04 zakończony");
