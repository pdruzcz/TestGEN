/**
 * Story 6.9, AC7 — skrypt CI uruchamiający axe-core (WCAG 2.1 AA)
 * na kluczowych stronach aplikacji przez Playwright + @axe-core/playwright.
 *
 * Uruchomienie: `npm run axe:ci` (wymaga działającej aplikacji pod
 * APP_BASE_URL, domyślnie http://localhost:4200).
 *
 * Wynik: raport w konsoli + kod wyjścia 1 przy jakimkolwiek naruszeniu
 * o poziomie critical/serious (AC7: 0 critical/serious violations).
 */
import { AxeBuilder } from "@axe-core/playwright";
import { chromium } from "playwright";
import {
  AXE_WCAG_TAGS,
  AxeViolationLike,
  blockingViolations,
  formatViolations,
} from "../src/app/shared/utils/axe-setup";

const BASE_URL = process.env["APP_BASE_URL"] ?? "http://localhost:4200";

/** Strony publiczne — dostępne bez uwierzytelnienia. */
const PUBLIC_ROUTES = ["/login", "/register", "/reset-password"];

/**
 * Strony wymagające zalogowania — skanowane, gdy podano dane logowania
 * (E2E_USER_EMAIL / E2E_USER_PASSWORD).
 */
const AUTHENTICATED_ROUTES = [
  "/dashboard",
  "/projects",
  "/settings/users",
  "/settings/profile",
];

async function main(): Promise<void> {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  const email = process.env["E2E_USER_EMAIL"];
  const password = process.env["E2E_USER_PASSWORD"];
  const routes = [...PUBLIC_ROUTES];

  if (email && password) {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard|select-tenant/);
    routes.push(...AUTHENTICATED_ROUTES);
  } else {
    console.warn(
      "Brak E2E_USER_EMAIL/E2E_USER_PASSWORD — skanuję tylko strony publiczne.",
    );
  }

  let blockingTotal = 0;

  for (const route of routes) {
    await page.goto(`${BASE_URL}${route}`, { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page })
      .withTags([...AXE_WCAG_TAGS])
      .analyze();
    const violations = results.violations as unknown as AxeViolationLike[];
    const blocking = blockingViolations(violations);
    blockingTotal += blocking.length;

    console.log(`\n=== ${route} ===`);
    console.log(
      `Naruszenia: ${violations.length} (blokujące critical/serious: ${blocking.length})`,
    );
    if (blocking.length > 0) {
      console.log(formatViolations(blocking));
    }
  }

  await browser.close();

  if (blockingTotal > 0) {
    console.error(
      `\nAC7 niespełnione: ${blockingTotal} naruszeń critical/serious.`,
    );
    process.exit(1);
  }
  console.log("\nAC7 spełnione: 0 naruszeń critical/serious (WCAG 2.1 AA).");
}

main().catch((error) => {
  console.error("Błąd axe-runner:", error);
  process.exit(1);
});
