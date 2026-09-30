import { AxeBuilder } from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import {
  PROJECT_ID,
  READY_DOCUMENT,
  expect,
  test,
} from "./fixtures/test-fixtures";

/**
 * Story 6.13, AC9 — audyt dostępności axe-core na kluczowych stronach.
 *
 * Konwencja zgodna ze Story 6.9 (accessibility/axe-runner.ts i
 * shared/utils/axe-setup): tagi WCAG 2.1 A/AA, próg zaliczenia =
 * 0 naruszeń o impact critical/serious.
 */
const AXE_WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function expectNoBlockingViolations(
  page: Page,
  route: string,
): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(AXE_WCAG_TAGS)
    .analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  expect(
    blocking,
    `Naruszenia critical/serious na ${route}: ${blocking
      .map((v) => `${v.id} (${v.impact})`)
      .join(", ")}`,
  ).toEqual([]);
}

test.describe("AC9 — dostępność (axe, WCAG 2.1 AA)", () => {
  test("/login — brak naruszeń critical/serious", async ({
    page,
    mockApi,
  }) => {
    void mockApi;
    await page.goto("/login");
    await expect(
      page.getByRole("heading", { name: "Logowanie" }),
    ).toBeVisible();
    await expectNoBlockingViolations(page, "/login");
  });

  test("/register — brak naruszeń critical/serious", async ({
    page,
    mockApi,
  }) => {
    void mockApi;
    await page.goto("/register");
    await expect(
      page.getByRole("heading", { name: "Rejestracja" }),
    ).toBeVisible();
    await expectNoBlockingViolations(page, "/register");
  });

  test("/dashboard — brak naruszeń critical/serious", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockDashboard();
    await page.goto("/dashboard");
    await expect(
      page.getByRole("heading", { name: /Witaj,/ }),
    ).toBeVisible();
    await expectNoBlockingViolations(page, "/dashboard");
  });

  test("strona uploadu dokumentów — brak naruszeń critical/serious", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockDocumentsList([READY_DOCUMENT]);
    await page.goto(`/projects/${PROJECT_ID}/documents`);
    await expect(
      page.getByRole("heading", { name: "Dokumentacja projektu" }),
    ).toBeVisible();
    await expectNoBlockingViolations(page, "documents");
  });

  test("strona analizy — brak naruszeń critical/serious", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockAnalysisPageData();
    await page.goto(`/projects/${PROJECT_ID}/analysis`);
    await expect(
      page.getByRole("heading", {
        name: "Konfiguracja i uruchomienie analizy",
      }),
    ).toBeVisible();
    await expectNoBlockingViolations(page, "analysis");
  });

  test("strona raportów — brak naruszeń critical/serious", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockReportSources();
    await page.goto(`/projects/${PROJECT_ID}/reports`);
    await expect(
      page.getByRole("heading", { name: "Generator raportów" }),
    ).toBeVisible();
    await expectNoBlockingViolations(page, "reports");
  });
});
