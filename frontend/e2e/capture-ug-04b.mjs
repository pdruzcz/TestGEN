/** Story 9.5 — re-zrzuty 03 (synchronizacja) i 06 (powiadomienia) przez window.scrollTo. */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const shot = async (p, n) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), fullPage: false }); console.log(`📸 ${n}`); };

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
page.setDefaultTimeout(15000);

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill("anna.demo@testgen.nexio.pl");
await page.locator('input[type="password"]').first().fill("Qa-Demo-2026!Podrecznik");
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);
const projects = await page.evaluate(async () => (await (await fetch("/api/v1/projects", { credentials: "include" })).json()));
const pid = projects.projects.find((p) => p.name.includes("Sklep internetowy"))?.id ?? projects.projects[0].id;

// 03: synchronizacja — przewiń pod formularz (sekcja ~950px)
await page.goto(`${BASE}/projects/${pid}/integrations`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await page.evaluate(() => window.scrollTo(0, 550));
await page.waitForTimeout(600);
await shot(page, "ug-04-03-integracje-sync");

// 06: powiadomienia — karta pod danymi profilu i hasłem
await page.goto(`${BASE}/settings/profile`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await page.evaluate(() => {
  const el = Array.from(document.querySelectorAll("h2, h3, mat-card-title, .mat-card-title"))
    .find((e) => (e.textContent ?? "").includes("Powiadomienia"));
  if (el) window.scrollTo(0, Math.max(0, el.getBoundingClientRect().top + window.scrollY - 80));
  else window.scrollTo(0, document.body.scrollHeight / 2);
});
await page.waitForTimeout(600);
await shot(page, "ug-04-06-ustawienia-powiadomienia");

await browser.close();
console.log("✅ re-zrzuty 03/06 zakończone");
