import { test as base, expect, Page } from "@playwright/test";

/**
 * Story 6.13 — wspólne fixtures E2E.
 *
 * Architektura: backend NIE działa podczas testów — wszystkie wywołania
 * API (/api/v1/**) są mockowane przez page.route().
 *
 * Sesja logowania: aplikacja używa ciasteczek HttpOnly ustawianych przez
 * backend (AuthService nie zapisuje tokenów w localStorage). Stan zalogowania
 * jest odtwarzany przez authGuard, który przy wejściu na chronioną trasę
 * woła GET /api/v1/users/me (fetchProfile). Wystarczy więc zamockować ten
 * endpoint, aby przeglądarka była "zalogowana" — dokładnie tak, jak przy
 * odświeżeniu strony z ważnym cookie.
 */

export const PROJECT_ID = "p-1";

/** Profil użytkownika — kształt zgodny z UserProfile (auth.service.ts). */
export const TEST_USER = {
  id: "u-1",
  tenantId: "t-1",
  email: "jan.kowalski@example.com",
  name: "Jan Kowalski",
  role: "owner",
  isActive: true,
  emailVerifiedAt: "2026-01-01T00:00:00Z",
  notificationPreferences: {},
  mfaEnabled: false,
};

/** Odpowiedź logowania — kształt zgodny z LoginResponse (auth.service.ts). */
export const LOGIN_OK_RESPONSE = {
  message: "Zalogowano pomyślnie",
  mfaRequired: false,
  mfaToken: null,
  tenantsRequired: false,
  preAuthToken: null,
  tenants: null,
};

/** Kształt zgodny z DashboardSummary (dashboard.service.ts). */
export const DASHBOARD_SUMMARY = {
  projects: [
    {
      id: PROJECT_ID,
      name: "Projekt Alfa",
      lastAnalysisAt: "2026-07-20T10:00:00Z",
      complianceScore: 87,
      testCasesCount: 42,
      status: "active",
    },
    {
      id: "p-2",
      name: "Projekt Beta",
      lastAnalysisAt: null,
      complianceScore: null,
      testCasesCount: 0,
      status: "analyzing",
    },
    {
      id: "p-3",
      name: "Projekt Gamma",
      lastAnalysisAt: "2026-07-01T08:30:00Z",
      complianceScore: 45,
      testCasesCount: 7,
      status: "completed",
    },
  ],
  statistics: {
    totalProjects: 3,
    analysesThisMonth: 5,
    avgCompliance: 76.5,
    totalTestCases: 49,
    activeUsers: 4,
  },
  planUsage: {
    plan: "professional",
    analysesUsed: 5,
    analysesLimit: 50,
    projectsCount: 3,
  },
};

/** Kształt zgodny z AuditLogList (dashboard.service.ts). */
export const AUDIT_LOGS = {
  items: [
    {
      id: "a-1",
      userId: "u-1",
      action: "project.created",
      resourceType: "project",
      resourceId: PROJECT_ID,
      details: null,
      createdAt: "2026-07-23T12:00:00Z",
      userEmail: "jan.kowalski@example.com",
    },
    {
      id: "a-2",
      userId: "u-1",
      action: "analysis.completed",
      resourceType: "project",
      resourceId: PROJECT_ID,
      details: null,
      createdAt: "2026-07-23T13:15:00Z",
      userEmail: "jan.kowalski@example.com",
    },
  ],
  total: 2,
};

/** Dokument gotowy — kształt zgodny z DocumentFile (document.service.ts). */
export const READY_DOCUMENT = {
  id: "doc-1",
  projectId: PROJECT_ID,
  filename: "specyfikacja.pdf",
  fileSize: 245_000,
  fileCategory: "documentation",
  docFormat: "pdf",
  pageCount: 12,
  createdAt: "2026-07-22T09:00:00Z",
  isCleanedUp: false,
  processingStatus: "ready",
  errorMessage: null,
  docType: "specyfikacja_wymagań",
  classificationConfidence: 92,
  classificationJustification: "Dokument zawiera wymagania funkcjonalne.",
};

/** Kształt zgodny z PreprocessingReport (preprocessing.service.ts). */
export const PREPROCESSING_REPORT = {
  projectId: PROJECT_ID,
  languages: [
    { language: "python", count: 12, loc: 3400 },
    { language: "typescript", count: 8, loc: 1900 },
  ],
  detectedFrameworks: ["fastapi", "angular"],
  totalLoc: 5300,
  unknownFiles: [],
};

/** Kształt zgodny z SecurityFinding (security-scan.service.ts). */
export const SECURITY_FINDING = {
  id: "sf-1",
  scanId: "scan-1",
  scanType: "sast",
  vulnerabilityType: "SQL Injection",
  severity: "critical",
  cweId: "CWE-89",
  owaspCategory: "A03:2021",
  filePath: "app/api/users.py",
  lineStart: 42,
  lineEnd: 44,
  codeSnippet: 'query = f"SELECT * FROM users WHERE id = {user_id}"',
  description: "Zapytanie SQL budowane przez konkatenację danych wejściowych.",
  confidence: 95,
  source: "semgrep",
  status: "open",
  taintPath: null,
  findingMetadata: null,
  recommendation: "Użyj zapytań parametryzowanych.",
  cvssScore: 9.8,
  cvssVector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
  priority: 1,
  effort: "low",
  escalationReason: null,
  createdAt: "2026-07-20T10:00:00Z",
};

/** Kształt zgodny z GapAnalysisSummary (gap-analysis.service.ts). */
export const GAP_SUMMARY = {
  totalRequirements: 20,
  totalCodeEntities: 35,
  missingCount: 2,
  differentCount: 1,
  extraCount: 0,
  inconsistentCount: 0,
  avgMatchScore: 0.84,
  coveragePercentage: 74,
};

/** Kształt zgodny z TestCaseListResponse (test-case.service.ts). */
export const TEST_CASES_RESPONSE = {
  testCases: [],
  total: 8,
  statusCounts: {
    ready: 5,
    passed: 3,
    failed: 0,
    skipped: 0,
    draft: 0,
    disabled: 0,
  },
};

interface MockOptions {
  status?: number;
  /** Ogranicz mock do metody HTTP; inne metody spadają do fallbacku. */
  method?: string;
  headers?: Record<string, string>;
}

/**
 * Pomocnik rejestrujący route'y API. Playwright dopasowuje route'y od
 * ostatnio zarejestrowanego — mocki dodane później w teście nadpisują
 * wcześniejsze (w tym domyślny fallback 404).
 */
export class ApiMock {
  constructor(private readonly page: Page) {}

  /**
   * Domyślny fallback: każde niezamockowane wywołanie /api/v1/** dostaje
   * 404 — serwisy FE obsługują to defensywnie (catchError / error branch),
   * a test nie wisi na realnym backendzie.
   */
  async installDefaults(): Promise<void> {
    await this.page.route("**/api/v1/**", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Endpoint niezamockowany w E2E" }),
      }),
    );
  }

  /** Zamockuj odpowiedź JSON dla wzorca URL (glob lub RegExp). */
  async mock(
    url: string | RegExp,
    body: unknown,
    options: MockOptions = {},
  ): Promise<void> {
    const { status = 200, method, headers } = options;
    await this.page.route(url, (route) => {
      if (method && route.request().method() !== method) {
        return route.fallback();
      }
      return route.fulfill({
        status,
        contentType: "application/json",
        headers,
        body: JSON.stringify(body),
      });
    });
  }

  /**
   * Sesja zalogowanego użytkownika — mock GET /users/me, z którego
   * authGuard odtwarza profil (auth cookie-based, patrz nagłówek pliku).
   */
  async mockSession(user: unknown = TEST_USER): Promise<void> {
    await this.mock("**/api/v1/users/me", user, { method: "GET" });
  }

  /** Poprawne logowanie: POST /auth/login + profil użytkownika. */
  async mockLoginSuccess(): Promise<void> {
    await this.mock("**/api/v1/auth/login", LOGIN_OK_RESPONSE, {
      method: "POST",
    });
    await this.mockSession();
  }

  /** Dane dashboardu: /dashboard/summary + /dashboard/audit-logs. */
  async mockDashboard(
    summary: unknown = DASHBOARD_SUMMARY,
    auditLogs: unknown = AUDIT_LOGS,
  ): Promise<void> {
    await this.mock("**/api/v1/dashboard/summary", summary, {
      method: "GET",
    });
    await this.mock("**/api/v1/dashboard/audit-logs*", auditLogs, {
      method: "GET",
    });
  }

  /**
   * Lista dokumentów projektu — body to tablica DocumentFile,
   * total w nagłówku X-Total-Count (patrz document.service.ts).
   */
  async mockDocumentsList(documents: unknown[]): Promise<void> {
    await this.mock(`**/api/v1/projects/${PROJECT_ID}/documents*`, documents, {
      method: "GET",
      headers: { "X-Total-Count": String(documents.length) },
    });
  }

  /** Dane strony konfiguracji analizy (/config + preprocessing-report). */
  async mockAnalysisPageData(): Promise<void> {
    await this.mock("**/api/v1/config", { engineMode: "native" }, {
      method: "GET",
    });
    await this.mock(
      `**/api/v1/projects/${PROJECT_ID}/preprocessing-report`,
      PREPROCESSING_REPORT,
      { method: "GET" },
    );
  }

  /**
   * Dane zbierane przez ReportService.generateReport() (Story 6.6) —
   * wszystkie endpointy agregacji raportu.
   */
  async mockReportSources(): Promise<void> {
    await this.mock(
      `**/api/v1/projects/${PROJECT_ID}/security-findings*`,
      { findings: [SECURITY_FINDING], total: 1, page: 1, pageSize: 200 },
      { method: "GET" },
    );
    await this.mock(
      `**/api/v1/projects/${PROJECT_ID}/gap-findings*`,
      { findings: [], total: 0, page: 1, size: 100, summary: GAP_SUMMARY },
      { method: "GET" },
    );
    await this.mock(
      `**/api/v1/projects/${PROJECT_ID}/gap-analysis/summary`,
      GAP_SUMMARY,
      { method: "GET" },
    );
    await this.mock(
      `**/api/v1/projects/${PROJECT_ID}/compliance`,
      { score: 82, totalFindings: 1, breakdown: { critical: 1 } },
      { method: "GET" },
    );
    await this.mock(
      `**/api/v1/projects/${PROJECT_ID}/compliance/modules`,
      [],
      { method: "GET" },
    );
    await this.mock(
      `**/api/v1/projects/${PROJECT_ID}/compliance/trend*`,
      { points: [] },
      { method: "GET" },
    );
    await this.mock("**/api/v1/test-cases*", TEST_CASES_RESPONSE, {
      method: "GET",
      headers: { "X-Total-Count": "8" },
    });
  }
}

interface E2eFixtures {
  /** Wspólne mocki API — z domyślnym fallbackiem 404 dla /api/v1/**. */
  mockApi: ApiMock;
  /** Strona z odtworzoną sesją zalogowanego użytkownika. */
  authenticatedPage: Page;
}

export const test = base.extend<E2eFixtures>({
  mockApi: async ({ page }, use) => {
    const api = new ApiMock(page);
    await api.installDefaults();
    await use(api);
  },
  authenticatedPage: async ({ page, mockApi }, use) => {
    await mockApi.mockSession();
    await use(page);
  },
});

export { expect };
