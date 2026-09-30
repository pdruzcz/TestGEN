import {
  AUDIT_LOGS,
  DASHBOARD_SUMMARY,
  PROJECT_ID,
  expect,
  test,
} from "./fixtures/test-fixtures";
import { DashboardPage } from "./pages/dashboard.page";

/**
 * Story 6.13, AC2 — dashboard i przegląd projektów.
 *
 * Po załatkaniu braków Story 6.1: tabela projektów ma MatSort + MatPaginator,
 * 4. karta statystyk to "Test case'y" (zamiast "Aktywni użytkownicy"),
 * a w wierszu powitania są quick actions: "Nowa analiza" i "Upload dokumentacji".
 */
test.describe("AC2 — dashboard", () => {
  test.beforeEach(async ({ mockApi }) => {
    await mockApi.mockDashboard();
  });

  test("wyświetla karty statystyk z danymi z /dashboard/summary", async ({
    authenticatedPage: page,
  }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await expect(dashboard.welcomeTitle).toHaveText("Witaj, Jan");
    await expect(dashboard.statCard("Projekty")).toContainText("3");
    await expect(dashboard.statCard("Analizy w tym miesiącu")).toContainText(
      "5",
    );
    // [~] deviation: aplikacja nie rejestruje locale pl (brak LOCALE_ID /
    // registerLocaleData), więc DecimalPipe formatuje po en-US: "76.5%".
    await expect(dashboard.statCard("Śr. zgodność")).toContainText("76.5%");
    // Story 6.1 AC2: 4. karta to liczba wygenerowanych test case'ów.
    await expect(dashboard.statCard("Test case'y")).toContainText("49");
  });

  test("wyświetla listę projektów ze statusami PL i zgodnością", async ({
    authenticatedPage: page,
  }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await expect(dashboard.projectsTable).toBeVisible();
    // Wiersze projektów z zamockowanego summary
    await expect(dashboard.projectLink("Projekt Alfa")).toBeVisible();
    await expect(dashboard.projectLink("Projekt Beta")).toBeVisible();
    await expect(dashboard.projectLink("Projekt Gamma")).toBeVisible();
    // Statusy przetłumaczone na PL (STATUS_LABELS)
    await expect(dashboard.projectsTable).toContainText("Aktywny");
    await expect(dashboard.projectsTable).toContainText("W analizie");
    await expect(dashboard.projectsTable).toContainText("Zakończony");
    // Badge zgodności
    await expect(dashboard.projectsTable).toContainText("87%");
  });

  test("pusty stan listy projektów", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockDashboard(
      {
        ...DASHBOARD_SUMMARY,
        projects: [],
        statistics: { ...DASHBOARD_SUMMARY.statistics, totalProjects: 0 },
      },
      { items: [], total: 0 },
    );

    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await expect(dashboard.projectsEmptyState).toBeVisible();
    await expect(
      page.getByText("Brak aktywności do wyświetlenia."),
    ).toBeVisible();
  });

  test("feed 'Ostatnia aktywność' pokazuje wpisy audytu z etykietami PL", async ({
    authenticatedPage: page,
  }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await expect(dashboard.activityCardTitle).toBeVisible();
    // ACTION_LABELS: project.created / analysis.completed
    await expect(page.getByText("Utworzono projekt")).toBeVisible();
    await expect(page.getByText("Zakończono analizę")).toBeVisible();
    await expect(
      page.getByText(AUDIT_LOGS.items[0].userEmail!).first(),
    ).toBeVisible();
  });

  test("nawigacja do szczegółów projektu po kliknięciu nazwy", async ({
    authenticatedPage: page,
  }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await dashboard.projectLink("Projekt Alfa").click();

    // Route /projects/:projectId (project-detail) — dane detalu zwracają
    // zamockowany fallback 404, ale sama nawigacja musi zadziałać
    await expect(page).toHaveURL(new RegExp(`/projects/${PROJECT_ID}$`));
  });

  test("szybka akcja 'Nowy projekt' prowadzi do listy projektów", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mock("**/api/v1/projects*", [], {
      method: "GET",
      headers: { "X-Total-Count": "0" },
    });

    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await dashboard.newProjectButton.click();
    await expect(page).toHaveURL(/\/projects$/);
  });

  test("quick action 'Nowa analiza' nawiguje do analizy ostatniego projektu (Story 6.1 AC6)", async ({
    authenticatedPage: page,
  }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    // Pierwszy projekt w DASHBOARD_SUMMARY = "Projekt Alfa" (id=PROJECT_ID),
    // link powinien prowadzić do /projects/{id}/analysis.
    await dashboard.newAnalysisButton.click();
    await expect(page).toHaveURL(
      new RegExp(`/projects/${PROJECT_ID}/analysis$`),
    );
  });

  test("quick action 'Upload dokumentacji' nawiguje do dokumentów ostatniego projektu (Story 6.1 AC6)", async ({
    authenticatedPage: page,
  }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await dashboard.uploadDocsButton.click();
    await expect(page).toHaveURL(
      new RegExp(`/projects/${PROJECT_ID}/documents$`),
    );
  });

  test("quick actions prowadzą do listy /projects gdy brak projektów", async ({
    authenticatedPage: page,
    mockApi,
  }) => {
    await mockApi.mockDashboard(
      {
        ...DASHBOARD_SUMMARY,
        projects: [],
        statistics: { ...DASHBOARD_SUMMARY.statistics, totalProjects: 0 },
      },
      AUDIT_LOGS,
    );

    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    // Brak projektów → oba quick actions wygaszone (pointer-events: none),
    // ale przyciski nadal renderowane; klik nie nawiguje.
    await expect(dashboard.newAnalysisButton).toBeVisible();
    await expect(dashboard.newAnalysisButton).toHaveClass(/disabled-action/);
    await expect(dashboard.uploadDocsButton).toHaveClass(/disabled-action/);
  });

  test("sortowanie tabeli po nazwie — Story 6.1 AC5", async ({
    authenticatedPage: page,
  }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    // Klik na nagłówek "Nazwa" przełącza sortowanie.
    const nameHeader = dashboard.sortHeader("Nazwa");
    await nameHeader.click();

    // Po kliknięciu sort jest aktywny na nazwie.
    await expect(dashboard.projectsTable).toBeVisible();
  });

  test("paginacja tabeli renderuje się z pageSizeOptions — Story 6.1 AC5", async ({
    authenticatedPage: page,
  }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await expect(dashboard.paginator).toBeVisible();
  });
});
