import {
  PROJECT_ID,
  READY_DOCUMENT,
  expect,
  test,
} from "./fixtures/test-fixtures";
import { UploadPage } from "./pages/upload.page";

/**
 * Story 6.13, AC3 — upload dokumentacji projektu
 * (/projects/:projectId/documents, document-upload.component.ts).
 *
 * Uwagi do realnego UI:
 * - walidacja formatu i rozmiaru jest FRONTENDOWA (handleFiles),
 * - limit rozmiaru to 100 MB (MAX_FILE_SIZE_BYTES), nie 50 MB jak w story —
 *   patrz [~] deviation w teście rozmiaru,
 * - komponent nie ma przycisku anulowania uploadu — patrz [~] deviation.
 */
test.describe("AC3 — upload dokumentów", () => {
  test("upload PDF poprawny — status 'Gotowy' po przetworzeniu", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    // Stanowy mock: przed uploadem lista pusta, po uploadzie 1 dokument ready
    let uploaded = false;
    await page.route(
      `**/api/v1/projects/${PROJECT_ID}/documents*`,
      (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: { "X-Total-Count": uploaded ? "1" : "0" },
          body: JSON.stringify(uploaded ? [READY_DOCUMENT] : []),
        }),
    );
    await page.route(
      `**/api/v1/projects/${PROJECT_ID}/upload-documents`,
      (route) => {
        uploaded = true;
        return route.fulfill({
          status: 202,
          contentType: "application/json",
          body: JSON.stringify({
            taskId: "task-doc-1",
            status: "accepted",
            statusUrl: "/api/v1/tasks/task-doc-1",
            message: "Przyjęto do przetwarzania",
          }),
        });
      },
    );
    // Polling statusu zadania parsowania (co 2 s) — od razu completed
    await mockApi.mock(
      "**/api/v1/tasks/task-doc-1",
      { taskId: "task-doc-1", status: "completed", result: null, error: null },
      { method: "GET" },
    );

    const upload = new UploadPage(page);
    await upload.goto();
    await expect(upload.emptyState).toBeVisible();

    await upload.uploadFile(
      "specyfikacja.pdf",
      "application/pdf",
      Buffer.from("%PDF-1.4\n%test-e2e"),
    );

    await expect(upload.successBanner).toContainText("Wysłano 1 dokumentów");
    const card = upload.documentCard("specyfikacja.pdf");
    await expect(card).toBeVisible();
    await expect(card).toContainText("Gotowy", { timeout: 15_000 });
    // Chip klasyfikacji (Story 2.3) z danych backendu
    await expect(card).toContainText("Specyfikacja wymagań");
    // Sekcja akcji dostępna, gdy jest gotowy dokument
    await expect(upload.analyzeButton).toBeVisible();
  });

  test("walidacja formatu — plik .exe odrzucony z komunikatem PL", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockDocumentsList([]);

    const upload = new UploadPage(page);
    await upload.goto();
    await expect(upload.pageTitle).toBeVisible();

    await upload.uploadFile(
      "wirus.exe",
      "application/octet-stream",
      Buffer.from("MZ"),
    );

    // Komunikat z handleFiles(): "Nieobsługiwany format: .exe. Dozwolone: ..."
    await expect(upload.errorBanner).toContainText(
      "Nieobsługiwany format: .exe",
    );
    await expect(upload.errorBanner).toContainText(".pdf");
  });

  test("walidacja rozmiaru — plik ponad limit odrzucony frontendowo", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    // [~] deviation: story mówi o limicie 50 MB, ale realny frontend ma
    // MAX_FILE_SIZE_BYTES = 100 MB. Testujemy realny limit (100 MB + 1 B).
    // Plik tworzony w kontekście przeglądarki, aby nie przesyłać 100 MB
    // przez protokół automatyzacji.
    await mockApi.mockDocumentsList([]);

    const upload = new UploadPage(page);
    await upload.goto();
    await expect(upload.pageTitle).toBeVisible();

    await upload.selectLargeFileInBrowser(
      "ogromny-dokument.pdf",
      "application/pdf",
      100 * 1024 * 1024 + 1,
    );

    // Komunikat z handleFiles(): "Plik przekracza limit 100.0 MB. ..."
    await expect(upload.errorBanner).toContainText("Plik przekracza limit");
    await expect(upload.errorBanner).toContainText("ogromny-dokument.pdf");
  });

  test("duplikat — błąd wysyłania przy odpowiedzi 409 z backendu", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    // [~] deviation: komponent nie ma dedykowanego komunikatu "duplikat" —
    // błąd HTTP uploadu pokazuje generyczne "Błąd wysyłania: ...".
    await mockApi.mockDocumentsList([]);
    await mockApi.mock(
      `**/api/v1/projects/${PROJECT_ID}/upload-documents`,
      { detail: "Dokument o tej nazwie już istnieje" },
      { method: "POST", status: 409 },
    );

    const upload = new UploadPage(page);
    await upload.goto();
    await expect(upload.pageTitle).toBeVisible();

    await upload.uploadFile(
      "specyfikacja.pdf",
      "application/pdf",
      Buffer.from("%PDF-1.4"),
    );

    await expect(upload.errorBanner).toContainText("Błąd wysyłania");
    // Dokument oznaczony jako nieudany na liście
    await expect(
      upload.documentCard("specyfikacja.pdf").getByText("Błąd", {
        exact: true,
      }),
    ).toBeVisible();
  });

  test("anulowanie w dialogu usuwania — dokument pozostaje na liście", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    // [~] deviation: UI nie ma przycisku anulowania trwającego uploadu —
    // najbliższy realny scenariusz "anuluj" to rezygnacja z usunięcia
    // dokumentu w dialogu potwierdzenia (document-delete-dialog).
    await mockApi.mockDocumentsList([READY_DOCUMENT]);

    const upload = new UploadPage(page);
    await upload.goto();
    await expect(upload.documentCard("specyfikacja.pdf")).toBeVisible();

    await upload.deleteButton("specyfikacja.pdf").click();
    await expect(
      page.getByRole("heading", { name: "Usunąć dokument?" }),
    ).toBeVisible();

    await page.getByRole("button", { name: "Anuluj" }).click();

    await expect(
      page.getByRole("heading", { name: "Usunąć dokument?" }),
    ).toBeHidden();
    await expect(upload.documentCard("specyfikacja.pdf")).toBeVisible();
  });

  test("usunięcie dokumentu — potwierdzenie w dialogu i komunikat sukcesu", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockDocumentsList([READY_DOCUMENT]);
    await mockApi.mock(
      `**/api/v1/projects/${PROJECT_ID}/files/${READY_DOCUMENT.id}`,
      {},
      { method: "DELETE", status: 200 },
    );

    const upload = new UploadPage(page);
    await upload.goto();
    await upload.deleteButton("specyfikacja.pdf").click();

    await page.getByRole("button", { name: "Usuń", exact: true }).click();

    await expect(upload.successBanner).toContainText("został usunięty");
    await expect(upload.documentCard("specyfikacja.pdf")).toBeHidden();
  });
});
