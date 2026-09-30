import { Locator, Page } from '@playwright/test';
import { PROJECT_ID } from '../fixtures/test-fixtures';

/**
 * Page Object — /projects/:projectId/analysis
 * (analysis.component.html / .ts).
 */
export class AnalysisPage {
  readonly pageTitle: Locator;
  readonly frameworkSelect: Locator;
  readonly startButton: Locator;
  readonly cancelButton: Locator;
  readonly runningStatus: Locator;
  readonly progressPercent: Locator;
  readonly completedStatus: Locator;
  readonly cancelledBanner: Locator;
  readonly failedBanner: Locator;
  readonly detectedTechnologies: Locator;

  constructor(readonly page: Page) {
    this.pageTitle = page.getByRole('heading', {
      name: 'Konfiguracja i uruchomienie analizy',
    });
    // mat-select dokleja wybraną wartość do accessible name — stabilniejszy
    // jest selektor elementu niż getByRole z nazwą
    this.frameworkSelect = page.locator('mat-select');
    // Etykieta przycisku zmienia się wraz ze stanem zadania („Uruchom
    // analizę” → „Uruchamianie...” → „Analiza w toku...” → „Uruchom
    // ponownie”), więc lokalizujemy go pozycją, nie nazwą.
    this.startButton = page.locator('.actions-row button').first();
    this.cancelButton = page.getByRole('button', { name: 'Anuluj analizę' });
    // Etykieta statusu żyje w karcie postępu; ten sam tekst pojawia się też
    // na przycisku uruchomienia, a w karcie „zakończone” towarzyszy mu
    // ligatura mat-icon — dlatego celujemy w konkretny element, nie w tekst.
    this.runningStatus = page.locator('.progress-card.running .progress-status');
    this.progressPercent = page.locator('.progress-pct');
    this.completedStatus = page.locator('.progress-card.completed .progress-status');
    this.cancelledBanner = page.getByText('Analiza została anulowana przez użytkownika.');
    this.failedBanner = page.getByText('Analiza nie powiodła się');
    this.detectedTechnologies = page.getByText('Wykryte technologie');
  }

  async goto(projectId: string = PROJECT_ID): Promise<void> {
    await this.page.goto(`/projects/${projectId}/analysis`);
  }

  /** Checkbox modułu po etykiecie PL (np. "Generowanie testów"). */
  moduleCheckbox(label: string): Locator {
    return this.page.getByRole('checkbox', { name: label });
  }

  /** Wybór frameworka testowego z mat-select. */
  async selectFramework(label: string): Promise<void> {
    await this.frameworkSelect.click();
    await this.page.getByRole('option', { name: label }).click();
  }

  async startAnalysis(): Promise<void> {
    await this.startButton.click();
  }

  async cancelAnalysis(): Promise<void> {
    await this.cancelButton.click();
  }
}
