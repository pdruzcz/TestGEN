/**
 * Story 9.2 — przepływ demo na żywym UI: nowy projekt → upload → analiza → wyniki.
 * Robi zrzuty + dumpuje DOM (przyciski) po każdym kroku — iteracyjne strojenie selektorów.
 * Uruchomienie (frontend/): node e2e/capture-ug-flow.mjs
 */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";

const BASE = "https://testgen.nexio.pl";
const EMAIL = "anna.demo@testgen.nexio.pl";
const PASSWORD = "Qa-Demo-2026!Podrecznik";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");
const DEMO_DIR = join(tmpdir(), "ug-demo");
const PROJECT_NAME = "Sklep internetowy (demo)";

const dump = async (page, label) => {
  const btns = await page.locator("button:visible").allTextContents().catch(() => []);
  console.log(`[${label}] BTN:`, JSON.stringify(btns.filter((t) => t.trim()).map((t) => t.trim().slice(0, 30))));
  const inputs = await page.locator("input:visible, textarea:visible, select:visible").evaluateAll((els) =>
    els.map((e) => ({ tag: e.tagName, type: e.type, ph: e.placeholder?.slice(0, 30), aria: e.getAttribute("aria-label")?.slice(0, 30) })),
  ).catch(() => []);
  console.log(`[${label}] IN:`, JSON.stringify(inputs));
};

const shot = async (page, name, opts = {}) => {
  await page.screenshot({ path: join(IMG_DIR, `${name}.png`), fullPage: false, ...opts });
  console.log(`📸 ${name}`);
};

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: "pl-PL" })).newPage();
mkdirSync(IMG_DIR, { recursive: true });

// logowanie
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator('input[type="email"], input[name="email"]').first().fill(EMAIL);
await page.locator('input[type="password"]').first().fill(PASSWORD);
await page.keyboard.press("Enter");
await page.waitForURL(/dashboard|projects/);
console.log("✅ zalogowano");

// --- Krok: nowy projekt ---
await page.goto(`${BASE}/projects`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
await shot(page, "ug-01-05-lista-projektow-pusta");
await page.getByRole("button", { name: /Nowy projekt/ }).first().click();
await page.waitForTimeout(800);
await dump(page, "dialog-nowy-projekt");
await shot(page, "ug-01-06-nowy-projekt-formularz");

const dialog = page.locator("mat-dialog-container, .cdk-overlay-pane").first();
const nameInput = dialog.locator("input:visible").first();
await nameInput.fill(PROJECT_NAME);
const descField = dialog.locator("textarea:visible").first();
if (await descField.count()) await descField.fill("Demonstracyjny projekt sklepu internetowego do podręcznika użytkownika.");
await dump(page, "dialog-wypelniony");
// submit: pierwszy przycisk potwierdzający w dialogu
const submit = dialog.getByRole("button", { name: /^(Dodaj|Zapisz|Utwórz|Zatwierdź|OK)/i }).first();
if (await submit.count()) await submit.click();
else await page.keyboard.press("Enter");
await page.waitForTimeout(2000);
console.log("URL po utworzeniu:", page.url());
await dump(page, "po-utworzeniu");

await browser.close();
console.log("✅ etap 1 (projekt) zakończony");
