import { Locator, Page } from "@playwright/test";

/**
 * Page Object — /dashboard (dashboard.component.ts).
 */
export class DashboardPage {
  readonly welcomeTitle: Locator;
  readonly newProjectButton: Locator;
  readonly newAnalysisButton: Locator;
  readonly uploadDocsButton: Locator;
  readonly projectsTable: Locator;
  readonly projectsEmptyState: Locator;
  readonly activityCardTitle: Locator;
  readonly paginator: Locator;
  /**
   * Przycisk "Wyloguj się" w treści dashboardu — zawężony do <main>, bo
   * navbar ma osobny przycisk z tym samym aria-label.
   */
  readonly logoutButton: Locator;
  readonly seeAllProjectsLink: Locator;

  constructor(readonly page: Page) {
    this.welcomeTitle = page.getByRole("heading", { name: /Witaj,/ });
    // <a mat-raised-button routerLink="/projects"> — rola "link"
    this.newProjectButton = page.getByRole("link", { name: "Nowy projekt" });
    // Story 6.1 AC6 — quick actions w wierszu powitania.
    this.newAnalysisButton = page.getByRole("link", { name: "Nowa analiza" });
    this.uploadDocsButton = page.getByRole("link", {
      name: "Upload dokumentacji",
    });
    this.projectsTable = page.getByRole("table", { name: "Lista projektów" });
    this.projectsEmptyState = page.getByText(
      "Brak projektów. Utwórz pierwszy projekt, aby rozpocząć analizę.",
    );
    this.activityCardTitle = page.getByRole("heading", {
      name: "Ostatnia aktywność",
    });
    // Story 6.1 AC5 — <mat-paginator> pod tabelą projektów.
    this.paginator = page.locator("mat-paginator");
    this.logoutButton = page
      .locator("main")
      .getByRole("button", { name: "Wyloguj się" });
    this.seeAllProjectsLink = page.getByRole("link", {
      name: /Zobacz wszystkie/,
    });
  }

  async goto(): Promise<void> {
    await this.page.goto("/dashboard");
  }

  /** Karta statystyk po etykiecie (np. "Projekty", "Śr. zgodność"). */
  statCard(label: string): Locator {
    return this.page
      .locator(".stat-card")
      .filter({ has: this.page.getByText(label, { exact: true }) });
  }

  /** Link do szczegółów projektu w tabeli (po nazwie projektu). */
  projectLink(name: string): Locator {
    return this.projectsTable.getByRole("link", { name });
  }

  /**
   * Story 6.1 AC5 — nagłówek sortowania w tabeli po etykiecie kolumny
   * (np. "Nazwa", "Status", "Zgodność"). Klik na <th mat-sort-header>
   * przełącza sortowanie; w Angular Material v21 cały nagłówek jest klikalny.
   */
  sortHeader(name: string): Locator {
    return this.projectsTable
      .locator("th.mat-sort-header")
      .filter({ hasText: name });
  }
}
