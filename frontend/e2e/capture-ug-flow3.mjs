/** Story 9.2 — etap 3: uruchomienie analizy + wyniki + TC + raporty. */
import { chromium } from "@playwright/test";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const EMAIL = "anna.demo@testgen.nexio.pl";
const PASSWORD = "Qa-Demo-2026!Podrecznik";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const shot = async (p, n, o = {}) => { await p.screenshot({ path: join(IMG_DIR, `${n}.png`), ...o }); console.log("📸 " + n); };
const dump = async (p, l) => {
  const b = await p.locator("button:visible").allTextContents().catch(() => []);
  console.log(`[${l}] BTN:`, JSON.stringify(b.filter(t => t.trim()).map(t => t.trim().slice(0, 30))));
};

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL);
await page.locator('input[type="password"]').first().fill(PASSWORD);
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);
const pid = (await page.evaluate(async () => (await (await fetch("/api/v1/projects", { credentials: "include" })).json()))).projects[0].id;

// --- Analiza ---
await page.goto(`${BASE}/projects/${pid}/analysis`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await dump(page, "analiza");
await shot(page, "ug-01-10-konfiguracja-analizy");
const run = page.getByRole("button", { name: /Uruchom analiz|Przeprowadź analiz|Rozpocznij/i }).first();
if (await run.count()) {
  await run.click();
  await page.waitForTimeout(1500);
  await shot(page, "ug-01-11-analiza-w-toku");
} else {
  console.log("!! nie znaleziono przycisku uruchomienia");
  await shot(page, "ug-01-10b-analiza-bez-przycisku", { fullPage: true });
}

// czekaj na zakończenie (poll API analiz)
let done = false;
for (let i = 0; i < 40 && !done; i++) {
  await page.waitForTimeout(3000);
  const st = await page.evaluate(async (pid) => {
    const r = await fetch(`/api/v1/projects/${pid}/analyses?page=1&size=5`, { credentials: "include" }).catch(() => null);
    if (!r || !r.ok) return null;
    return await r.json();
  }, pid).catch(() => null);
  if (st) console.log(`poll ${i}:`, JSON.stringify(st).slice(0, 220));
  done = st && JSON.stringify(st).includes("COMPLETED") || st && JSON.stringify(st).includes("completed");
}
await page.goto(`${BASE}/projects/${pid}/analysis`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot(page, "ug-01-11b-analiza-historia");

// --- Wyniki ---
await page.goto(`${BASE}/projects/${pid}/results`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await shot(page, "ug-01-12-wyniki");
await shot(page, "ug-01-12b-wyniki-calosc", { fullPage: true });

// --- Test case'y ---
await page.goto(`${BASE}/projects/${pid}/test-cases`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await shot(page, "ug-01-15-przypadki-testowe");
await shot(page, "ug-01-15b-przypadki-calosc", { fullPage: true });

// --- Raporty ---
await page.goto(`${BASE}/projects/${pid}/reports`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await shot(page, "ug-01-17-raporty");

await browser.close();
console.log("✅ etap 3 zakończony");
