import { PROJECT_ID, expect, test } from "./fixtures/test-fixtures";
import { ReportPage } from "./pages/report.page";
import type { ApiMock } from "./fixtures/test-fixtures";
import type { Page } from "@playwright/test";

/**
 * Story 6.13, AC5 — generowanie i eksport raportów
 * (/projects/:projectId/reports, Story 6.6/6.7).
 *
 * ReportService agreguje dane z wielu endpointów (security-findings,
 * gap-findings, compliance, trend, test-cases) — wszystkie zamockowane
 * w mockApi.mockReportSources().
 */
test.describe("AC5 — raporty", () => {
  test.beforeEach(async ({ mockApi }) => {
    await mockApi.mockReportSources();
  });

  /** Mock pełnego przepływu eksportu: zlecenie → status done → pobranie. */
  async function mockExportFlow(
    mockApi: ApiMock,
    page: Page,
    options: {
      exportId: string;
      format: string;
      filename: string;
      contentType: string;
      fileBody: string;
    },
  ): Promise<void> {
    await mockApi.mock(
      `**/api/v1/projects/${PROJECT_ID}/reports/export`,
      { exportId: options.exportId, status: "pending" },
      { method: "POST", status: 202 },
    );
    await mockApi.mock(
      `**/api/v1/exports/${options.exportId}/status`,
      {
        exportId: options.exportId,
        status: "done",
        exportFormat: options.format,
        filename: options.filename,
        error: null,
      },
      { method: "GET" },
    );
    // Odpowiedź binarna z Content-Disposition (AC8 story 6.7)
    await page.route(
      `**/api/v1/exports/${options.exportId}/download`,
      (route) =>
        route.fulfill({
          status: 200,
          contentType: options.contentType,
          headers: {
            "Content-Disposition": `attachment; filename="${options.filename}"`,
          },
          body: Buffer.from(options.fileBody),
        }),
    );
  }

  test("generowanie executive summary — KPI i wnioski PL", async ({
    authenticatedPage: page,
  }) => {
    const report = new ReportPage(page);
    await report.goto();
    await expect(report.pageTitle).toBeVisible();

    await report.generate("executive");

    await expect(
      report.reportTitle("Raport — podsumowanie wykonawcze"),
    ).toBeVisible();
    // Wniosek zbudowany z compliance.score = 82 (buildConclusions)
    await expect(report.preview).toContainText(
      "Zgodność oprogramowania z dokumentacją wynosi 82%",
    );
    // Wniosek o problemach krytycznych (1 finding critical)
    await expect(report.preview).toContainText(
      "Wykryto 1 problemów o znaczeniu krytycznym",
    );
  });

  test("generowanie raportu technicznego — lista ustaleń z detalami", async ({
    authenticatedPage: page,
  }) => {
    const report = new ReportPage(page);
    await report.goto();

    await report.generate("technical");

    await expect(
      report.reportTitle("Raport — szczegóły techniczne"),
    ).toBeVisible();
    // Ustalenie z zamockowanego security-findings
    await expect(report.preview).toContainText("SQL Injection");
    await expect(report.preview).toContainText("CWE-89");
  });

  test("podgląd raportu 'oba' — sekcje executive + techniczne i pasek eksportu", async ({
    authenticatedPage: page,
  }) => {
    const report = new ReportPage(page);
    await report.goto();

    await report.generate("both");

    await expect(
      report.reportTitle(/Raport pełny — podsumowanie i szczegóły/),
    ).toBeVisible();
    await expect(
      report.preview.getByRole("heading", {
        name: "Szczegóły techniczne",
        exact: true,
      }),
    ).toBeVisible();
    // Pasek eksportu (6 formatów) + przycisk druku
    await expect(report.exportGroup).toBeVisible();
    await expect(report.exportButton("PDF")).toBeVisible();
    await expect(report.exportButton("Excel")).toBeVisible();
    await expect(report.printButton).toBeVisible();
  });

  test("eksport PDF — pobranie pliku raport.pdf", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockExportFlow(mockApi, page, {
      exportId: "exp-1",
      format: "pdf",
      filename: "raport.pdf",
      contentType: "application/pdf",
      fileBody: "%PDF-1.4\n%raport-e2e",
    });

    const report = new ReportPage(page);
    await report.goto();
    await report.generate("executive");
    await expect(report.exportButton("PDF")).toBeEnabled();

    const downloadPromise = page.waitForEvent("download");
    await report.exportPdf();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe("raport.pdf");
    // Snackbar potwierdzenia pobrania (export-buttons.component.ts)
    await expect(page.getByText("Pobrano plik: raport.pdf")).toBeVisible();
  });

  test("eksport CSV — pobranie pliku raport.csv", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockExportFlow(mockApi, page, {
      exportId: "exp-2",
      format: "csv",
      filename: "raport.csv",
      contentType: "text/csv",
      fileBody: "id;tytul;severity\nsf-1;SQL Injection;critical\n",
    });

    const report = new ReportPage(page);
    await report.goto();
    await report.generate("technical");
    await expect(report.exportButton("CSV")).toBeEnabled();

    const downloadPromise = page.waitForEvent("download");
    await report.exportCsv();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe("raport.csv");
    await expect(page.getByText("Pobrano plik: raport.csv")).toBeVisible();
  });
});
