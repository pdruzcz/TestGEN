import { PROJECT_ID, expect, test } from './fixtures/test-fixtures';
import { AnalysisPage } from './pages/analysis.page';

/**
 * Story 6.13, AC4 — konfiguracja i uruchomienie analizy
 * (/projects/:projectId/analysis, analysis.component.html/.ts).
 *
 * Polling statusu zadania odbywa się co 5 s (startPolling) — mocki statusów
 * zwracają kolejne fazy przez licznik wywołań.
 */
test.describe('AC4 — konfiguracja i przebieg analizy', () => {
  test.beforeEach(async ({ mockApi }) => {
    await mockApi.mockAnalysisPageData();
  });

  test('konfiguracja — moduły i framework, bez pola „Tryb silnika”', async ({ authenticatedPage: page }) => {
    const analysis = new AnalysisPage(page);
    await analysis.goto();
    await expect(analysis.pageTitle).toBeVisible();

    // Domyślnie moduł "Analiza kodu"
    await expect(analysis.moduleCheckbox('Analiza kodu')).toBeChecked();
    // Story 6.3-zakończenie: engine_mode jest config-only — formularz nie
    // eksponuje trybu silnika ani opcji LLM
    await expect(page.getByText('Tryb silnika')).toBeHidden();
    await expect(page.getByRole('radio')).toHaveCount(0);
    await expect(page.getByText('Opcje zaawansowane LLM')).toBeHidden();

    // Dodanie modułu i zmiana frameworka testowego
    await analysis.moduleCheckbox('Generowanie testów').check();
    await analysis.selectFramework('Cypress');
    await expect(analysis.frameworkSelect).toContainText('Cypress');

    // Statystyki z preprocessing-report (12 + 8 plików) — zawężone do
    // karty statystyk, aby uniknąć kolizji strict mode z innymi "20"
    await expect(page.locator('.stats-card').getByText('20', { exact: true })).toBeVisible();
    await expect(analysis.startButton).toBeEnabled();
  });

  test('walidacja — brak modułów blokuje przycisk uruchomienia', async ({ authenticatedPage: page }) => {
    const analysis = new AnalysisPage(page);
    await analysis.goto();

    await analysis.moduleCheckbox('Analiza kodu').uncheck();

    await expect(analysis.startButton).toBeDisabled();
  });

  test("uruchomienie analizy — POST /analyze i stan 'Analiza w toku'", async ({ authenticatedPage: page, mockApi }) => {
    await mockApi.mock(
      `**/api/v1/projects/${PROJECT_ID}/analyze`,
      { taskId: 'task-9' },
      { method: 'POST', status: 202 },
    );
    await mockApi.mock(
      '**/api/v1/tasks/task-9',
      {
        taskId: 'task-9',
        status: 'running',
        progress: 20,
        currentStep: 'preprocessing',
        resultUrl: null,
        error: null,
      },
      { method: 'GET' },
    );

    const analysis = new AnalysisPage(page);
    await analysis.goto();
    await analysis.startAnalysis();

    await expect(analysis.runningStatus).toBeVisible();
    // Wskaźniki etapów (AC4 story 6.3) widoczne podczas analizy
    await expect(page.getByText('Kolejkowanie')).toBeVisible();
    await expect(page.getByText('Generowanie testów')).toBeVisible();
    await expect(analysis.startButton).toBeDisabled();
  });

  test('obserwacja postępu — kolejne pollingi aż do zakończenia', async ({ authenticatedPage: page, mockApi }) => {
    await mockApi.mock(
      `**/api/v1/projects/${PROJECT_ID}/analyze`,
      { taskId: 'task-9' },
      { method: 'POST', status: 202 },
    );
    // Sekwencja statusów: 1. polling → running 40%, kolejne → completed
    let poll = 0;
    await page.route('**/api/v1/tasks/task-9', (route) => {
      poll += 1;
      const body =
        poll === 1
          ? {
              taskId: 'task-9',
              status: 'running',
              progress: 40,
              currentStep: 'analysis',
              resultUrl: null,
              error: null,
            }
          : {
              taskId: 'task-9',
              status: 'completed',
              progress: 100,
              currentStep: 'export',
              resultUrl: null,
              error: null,
            };
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      });
    });

    const analysis = new AnalysisPage(page);
    await analysis.goto();
    await analysis.startAnalysis();

    // Pierwszy polling (po ~5 s): 40% i etap "Analiza"
    await expect(analysis.progressPercent).toHaveText('40%', {
      timeout: 10_000,
    });
    // Drugi polling (po ~10 s): analiza zakończona
    await expect(analysis.completedStatus).toBeVisible({ timeout: 15_000 });
    // Wykryte technologie z ponownie załadowanego preprocessing-report
    await expect(analysis.detectedTechnologies).toBeVisible();
    await expect(page.getByText('python (12)')).toBeVisible();
  });

  test('anulowanie analizy — POST /cancel i banner anulowania', async ({ authenticatedPage: page, mockApi }) => {
    await mockApi.mock(
      `**/api/v1/projects/${PROJECT_ID}/analyze`,
      { taskId: 'task-9' },
      { method: 'POST', status: 202 },
    );
    await mockApi.mock(
      '**/api/v1/tasks/task-9',
      {
        taskId: 'task-9',
        status: 'running',
        progress: 20,
        currentStep: 'preprocessing',
        resultUrl: null,
        error: null,
      },
      { method: 'GET' },
    );
    await mockApi.mock('**/api/v1/tasks/task-9/cancel', { taskId: 'task-9', status: 'cancelled' }, { method: 'POST' });

    const analysis = new AnalysisPage(page);
    await analysis.goto();
    await analysis.startAnalysis();

    await expect(analysis.cancelButton).toBeVisible();
    await analysis.cancelAnalysis();

    await expect(analysis.cancelledBanner).toBeVisible();
    // Formularz konfiguracji wraca, przycisk pozwala spróbować ponownie
    await expect(page.getByRole('button', { name: 'Spróbuj ponownie' })).toBeVisible();
  });
});
