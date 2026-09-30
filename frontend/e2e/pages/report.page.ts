import { Locator, Page } from "@playwright/test";
import { PROJECT_ID } from "../fixtures/test-fixtures";

/**
 * Page Object — /projects/:projectId/reports
 * (reports.component.html + report-preview / export-buttons).
 */
export class ReportPage {
  readonly pageTitle: Locator;
  readonly executiveRadio: Locator;
  readonly technicalRadio: Locator;
  readonly bothRadio: Locator;
  readonly generateButton: Locator;
  readonly errorCard: Locator;
  readonly preview: Locator;
  readonly printButton: Locator;
  readonly exportGroup: Locator;

  constructor(readonly page: Page) {
    this.pageTitle = page.getByRole("heading", {
      name: "Generator raportów",
    });
    // Opis opcji „Oba raporty” zawiera nazwy dwóch pozostałych, więc regexy
    // muszą być zakotwiczone na początku dostępnej nazwy.
    this.executiveRadio = page.getByRole("radio", {
      name: /^Podsumowanie wykonawcze/,
    });
    this.technicalRadio = page.getByRole("radio", {
      name: /^Szczegóły techniczne/,
    });
    this.bothRadio = page.getByRole("radio", { name: /Oba raporty/ });
    this.generateButton = page.getByRole("button", {
      name: "Generuj raport",
    });
    this.errorCard = page.getByRole("alert");
    this.preview = page.getByLabel("Podgląd raportu");
    this.printButton = page.getByRole("button", { name: "Drukuj" });
    this.exportGroup = page.getByRole("group", { name: "Eksport raportu" });
  }

  async goto(projectId: string = PROJECT_ID): Promise<void> {
    await this.page.goto(`/projects/${projectId}/reports`);
  }

  /** Tytuł raportu w podglądzie (np. "Raport — podsumowanie wykonawcze"). */
  reportTitle(name: string | RegExp): Locator {
    return this.preview.getByRole("heading", { name });
  }

  /** Przycisk eksportu po etykiecie formatu (PDF, HTML, CSV, ...). */
  exportButton(formatLabel: string): Locator {
    return this.page.getByRole("button", {
      name: `Eksportuj jako ${formatLabel}`,
    });
  }

  async generate(type: "executive" | "technical" | "both"): Promise<void> {
    const radio =
      type === "executive"
        ? this.executiveRadio
        : type === "technical"
          ? this.technicalRadio
          : this.bothRadio;
    await radio.check();
    await this.generateButton.click();
  }

  async exportPdf(): Promise<void> {
    await this.exportButton("PDF").click();
  }

  async exportCsv(): Promise<void> {
    await this.exportButton("CSV").click();
  }
}
