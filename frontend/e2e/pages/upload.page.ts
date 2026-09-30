import { Locator, Page } from "@playwright/test";
import { PROJECT_ID } from "../fixtures/test-fixtures";

/**
 * Page Object — /projects/:projectId/documents
 * (document-upload.component.ts).
 */
export class UploadPage {
  readonly pageTitle: Locator;
  readonly dropZone: Locator;
  readonly fileInput: Locator;
  readonly errorBanner: Locator;
  readonly successBanner: Locator;
  readonly documentCards: Locator;
  readonly emptyState: Locator;
  readonly analyzeButton: Locator;

  constructor(readonly page: Page) {
    this.pageTitle = page.getByRole("heading", {
      name: "Dokumentacja projektu",
    });
    this.dropZone = page.getByRole("button", {
      name: "Strefa drag-and-drop dla dokumentów",
    });
    this.fileInput = page.locator('input[type="file"]');
    this.errorBanner = page.getByRole("alert");
    this.successBanner = page.getByRole("status").filter({
      hasNot: page.locator("mat-spinner"),
    });
    this.documentCards = page.locator(".document-card");
    this.emptyState = page.getByText(/Brak dokumentów\./);
    this.analyzeButton = page.getByRole("button", {
      name: /Analizuj dokumentację/,
    });
  }

  async goto(projectId: string = PROJECT_ID): Promise<void> {
    await this.page.goto(`/projects/${projectId}/documents`);
  }

  /** Upload pliku z bufora (bez fizycznego pliku na dysku). */
  async uploadFile(
    name: string,
    mimeType: string,
    buffer: Buffer,
  ): Promise<void> {
    await this.fileInput.setInputFiles({ name, mimeType, buffer });
  }

  /**
   * Wybór pliku o zadanym rozmiarze utworzonego w kontekście przeglądarki —
   * pozwala walidować limit rozmiaru bez przesyłania ~100 MB przez protokół
   * automatyzacji (co byłoby wolne i niestabilne).
   */
  async selectLargeFileInBrowser(
    name: string,
    mimeType: string,
    sizeBytes: number,
  ): Promise<void> {
    await this.fileInput.evaluate(
      (input, args) => {
        const el = input as HTMLInputElement;
        const file = new File(
          [new ArrayBuffer(args.sizeBytes)],
          args.name,
          { type: args.mimeType },
        );
        const dt = new DataTransfer();
        dt.items.add(file);
        el.files = dt.files;
        el.dispatchEvent(new Event("change", { bubbles: true }));
      },
      { name, mimeType, sizeBytes },
    );
  }

  /** Karta dokumentu po nazwie pliku. */
  documentCard(filename: string): Locator {
    return this.documentCards.filter({ hasText: filename });
  }

  /** Przycisk usunięcia dokumentu w karcie o zadanej nazwie pliku. */
  deleteButton(filename: string): Locator {
    return this.documentCard(filename).getByRole("button", {
      name: "Usuń dokument",
    });
  }
}
