/**
 * Story 9.2 (AC2) — przechwytywanie zrzutów do podręcznika użytkownika
 * z REALNEGO, wdrożonego UI (https://testgen.nexio.pl). Nie mockupy.
 *
 * Uruchomienie (z katalogu frontend/):
 *   node e2e/capture-ug-shots.mjs [filtr]
 * Wynik: docs/final/user-guide/img/ug-01-xx-*.png
 *
 * Etap 1 (ten plik, bez argumentu): logowanie + ekrany statyczne.
 * Etap 2 (argument "flow"): projekt demo → upload → analiza → wyniki.
 */

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

const BASE = "https://testgen.nexio.pl";
const EMAIL = "anna.demo@testgen.nexio.pl";
const PASSWORD = "Qa-Demo-2026!Podrecznik";
const IMG_DIR = resolve("..", "docs", "final", "user-guide", "img");

const ONLY = process.argv[2] ?? "";

async function shot(page, name, { fullPage = false, clip = null } = {}) {
  const file = join(IMG_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage, ...(clip ? { clip } : {}) });
  console.log(`📸 ${name}.png`);
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  const email = page.locator('input[type="email"], input[name="email"], input[formcontrolname="email"]').first();
  await email.fill(EMAIL);
  const pass = page.locator('input[type="password"]').first();
  await pass.fill(PASSWORD);
  await page.keyboard.press("Enter");
  await page.waitForURL(/dashboard|projects/, { timeout: 20000 });
  await page.waitForTimeout(1500);
}

async function run() {
  mkdirSync(IMG_DIR, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.5,
    locale: "pl-PL",
  });
  const page = await context.newPage();

  // --- Ekrany publiczne ---
  if (!ONLY) {
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await shot(page, "ug-01-01-logowanie");

    await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await shot(page, "ug-01-02-rejestracja");

    await page.goto(`${BASE}/verify-email`, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(800);
    await shot(page, "ug-01-03-weryfikacja-email");
  }

  // --- Zalogowana przestrzeń ---
  await login(page);

  if (!ONLY) {
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    await shot(page, "ug-01-04-dashboard");

    // pasek dostępności — rozwinięty
    const a11y = page.locator("app-accessibility-toolbar, .accessibility-toolbar").first();
    if (await a11y.count()) {
      await a11y.click().catch(() => {});
      await page.waitForTimeout(400);
      await shot(page, "ug-01-23-pasek-dostepnosci");
    }

    // powiadomienia (dzwonek)
    const bell = page.locator("app-notification-bell button, button[aria-label*='owiadomien'], .notification-bell button").first();
    if (await bell.count()) {
      await bell.click().catch(() => {});
      await page.waitForTimeout(600);
      await shot(page, "ug-01-22-powiadomienia");
      await page.keyboard.press("Escape");
    }

    // menu profilowe
    const profile = page.locator("button:has-text('Anna'), [matbutton]:has-text('anna.demo'), .user-menu button").first();
    if (await profile.count()) {
      await profile.click().catch(() => {});
      await page.waitForTimeout(500);
      await shot(page, "ug-01-20-menu-profilu");
      await page.keyboard.press("Escape");
    }

    await page.goto(`${BASE}/settings/profile`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    await shot(page, "ug-01-21-ustawienia-profil", { fullPage: true });

    await page.goto(`${BASE}/billing/plans`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    await shot(page, "ug-01-25-plany", { fullPage: true });

    await page.goto(`${BASE}/billing/usage`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    await shot(page, "ug-01-26-zuzycie", { fullPage: true });

    // wysoki kontrast (toolbar ma przycisk po rozwinięciu)
    await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    const hcToggle = page.locator("app-accessibility-toolbar button:has-text('ontrast'), app-accessibility-toolbar button").nth(1);
    if (await hcToggle.count()) {
      await page.locator("app-accessibility-toolbar").first().click().catch(() => {});
      await page.waitForTimeout(300);
      await hcToggle.click().catch(() => {});
      await page.waitForTimeout(500);
      await shot(page, "ug-01-24-wysoki-kontrast");
      await hcToggle.click().catch(() => {}); // przywróć
    }
  }

  if (ONLY === "mobile") {
    const mctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
      locale: "pl-PL",
    });
    const mpage = await mctx.newPage();
    await login(mpage);
    await mpage.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
    await mpage.waitForTimeout(1200);
    await shot(mpage, "ug-01-27-mobilny");
    await mctx.close();
  }

  await browser.close();
  console.log("✅ Gotowe");
}

run().catch((e) => {
  console.error("❌", e);
  process.exit(1);
});
