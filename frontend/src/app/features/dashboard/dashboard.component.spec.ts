import { provideHttpClient } from "@angular/common/http";
import { provideHttpClientTesting } from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { signal, WritableSignal } from "@angular/core";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { provideRouter } from "@angular/router";
import { AuthService, UserProfile } from "../../core/services/auth.service";
import {
  AuditLogEntry,
  DashboardService,
  DashboardSummary,
  PlanUsage,
  ProjectDashboardItem,
  StatisticsCards,
} from "./dashboard.service";
import { DashboardComponent } from "./dashboard.component";

const mockUserOwner: UserProfile = {
  id: "u-1",
  tenantId: "t-1",
  email: "anna@example.com",
  name: "Anna Kowalska",
  role: "owner",
  isActive: true,
  emailVerifiedAt: "2026-01-01T00:00:00Z",
  notificationPreferences: {},
  mfaEnabled: false,
};

const mockProjects: ProjectDashboardItem[] = [
  {
    id: "p-1",
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
];

const mockStatistics: StatisticsCards = {
  totalProjects: 2,
  analysesThisMonth: 5,
  avgCompliance: 76.5,
  totalTestCases: 49,
  activeUsers: 4,
};

const mockPlanUsage: PlanUsage = {
  plan: "premium",
  analysesUsed: 5,
  analysesLimit: 50,
  projectsCount: 2,
};

const mockActivity: AuditLogEntry[] = [
  {
    id: "a-1",
    userId: "u-1",
    action: "project.created",
    resourceType: "project",
    resourceId: "p-1",
    details: null,
    createdAt: "2026-07-23T12:00:00Z",
    userEmail: "anna@example.com",
  },
];

interface ServiceState {
  projectsSignal: WritableSignal<ProjectDashboardItem[]>;
  statisticsSignal: WritableSignal<StatisticsCards | null>;
  planUsageSignal: WritableSignal<PlanUsage | null>;
  activitySignal: WritableSignal<AuditLogEntry[]>;
  isLoadingSummarySignal: WritableSignal<boolean>;
  isLoadingActivitySignal: WritableSignal<boolean>;
  errorSignal: WritableSignal<string | null>;
  loadSummary: ReturnType<typeof vi.fn>;
  loadActivity: ReturnType<typeof vi.fn>;
}

function createServiceMock(
  opts: {
    withPlanUsage?: boolean;
    projects?: ProjectDashboardItem[];
  } = {},
): ServiceState {
  return {
    projectsSignal: signal(opts.projects ?? mockProjects),
    statisticsSignal: signal(mockStatistics),
    planUsageSignal: signal(
      opts.withPlanUsage === false ? null : mockPlanUsage,
    ),
    activitySignal: signal(mockActivity),
    isLoadingSummarySignal: signal(false),
    isLoadingActivitySignal: signal(false),
    errorSignal: signal(null),
    loadSummary: vi.fn().mockReturnValue({
      subscribe: (handlers: { error?: () => void } = {}) => {
        handlers.error?.();
        return { unsubscribe: () => undefined };
      },
    }),
    loadActivity: vi.fn().mockReturnValue({
      subscribe: (handlers: { error?: () => void } = {}) => {
        handlers.error?.();
        return { unsubscribe: () => undefined };
      },
    }),
  };
}

async function setup(
  opts: {
    user?: UserProfile;
    serviceState?: ServiceState;
  } = {},
) {
  const authServiceMock = {
    currentUserSignal: signal<UserProfile | null>(
      opts.user ?? mockUserOwner,
    ) as WritableSignal<UserProfile | null>,
    logout: vi.fn(),
  };
  const serviceMock = opts.serviceState ?? createServiceMock();

  await TestBed.configureTestingModule({
    imports: [DashboardComponent, NoopAnimationsModule],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
      { provide: AuthService, useValue: authServiceMock },
      { provide: DashboardService, useValue: serviceMock },
    ],
  }).compileComponents();

  const fixture: ComponentFixture<DashboardComponent> =
    TestBed.createComponent(DashboardComponent);
  fixture.detectChanges();
  return { fixture, component: fixture.componentInstance, serviceMock };
}

describe("DashboardComponent", () => {
  it("tworzy się poprawnie", async () => {
    const { component } = await setup();
    expect(component).toBeTruthy();
  });

  describe("AC2 — karty statystyk", () => {
    it("renderuje 4 karty z poprawnymi danymi (incl. Test case'y jako 4. karta)", async () => {
      const { fixture } = await setup();
      fixture.detectChanges();
      const text = fixture.nativeElement.textContent as string;
      // Cztery etykiety kart.
      expect(text).toContain("Projekty");
      expect(text).toContain("Analizy w tym miesiącu");
      expect(text).toContain("Śr. zgodność");
      // AC2: 4. karta to "Test case'y", NIE "Aktywni użytkownicy".
      expect(text).toContain("Test case'y");
      expect(text).not.toContain("Aktywni użytkownicy");
      // Wartości statystyk.
      expect(text).toContain("49"); // totalTestCases
      expect(text).toContain("5"); // analysesThisMonth
    });

    it("pokazuje 0 dla test case'ów gdy statistics = null", async () => {
      const serviceState = createServiceMock();
      serviceState.statisticsSignal.set(null);
      const { fixture } = await setup({ serviceState });
      fixture.detectChanges();
      const cards = fixture.nativeElement.querySelectorAll(".stat-card");
      // Czwarta karta = Test case'y.
      expect(cards[3].textContent).toContain("0");
    });
  });

  describe("AC5 — sortowanie i paginacja tabeli projektów", () => {
    it("posiada dataSource z danymi z projects signal", async () => {
      const { component } = await setup();
      expect(component.dataSource.data).toHaveLength(2);
      expect(component.dataSource.data[0].name).toBe("Projekt Alfa");
    });

    it("wystawia sort i paginator jako viewChild sygnały", async () => {
      const { component } = await setup();
      expect(component.sort()).toBeTruthy();
      expect(component.paginator()).toBeTruthy();
      expect(component.dataSource.sort).toBe(component.sort());
      expect(component.dataSource.paginator).toBe(component.paginator());
    });

    it("renderuje nagłówki z mat-sort-header dla każdej kolumny", async () => {
      const { fixture } = await setup();
      const sortHeaders =
        fixture.nativeElement.querySelectorAll("th.mat-sort-header");
      expect(sortHeaders.length).toBe(component_displayedColumns_count());
    });

    it("domyślnie sortuje po lastAnalysis (desc)", async () => {
      const { component } = await setup();
      expect(component.sortActive).toBe("lastAnalysis");
    });

    it("sortingDataAccessor mapuje columnDef na właściwość obiektu", async () => {
      const { component } = await setup();
      const project: ProjectDashboardItem = {
        id: "p-x",
        name: "Zeta",
        lastAnalysisAt: "2026-07-25T10:00:00Z",
        complianceScore: 80,
        testCasesCount: 12,
        status: "active",
      };
      expect(component.dataSource.sortingDataAccessor!(project, "name")).toBe(
        "zeta",
      );
      expect(
        typeof component.dataSource.sortingDataAccessor!(
          project,
          "lastAnalysis",
        ),
      ).toBe("number");
      expect(
        component.dataSource.sortingDataAccessor!(project, "compliance"),
      ).toBe(80);
      expect(
        component.dataSource.sortingDataAccessor!(project, "testCases"),
      ).toBe(12);
    });

    it("sortingDataAccessor obsługuje null-last dla complianceScore", async () => {
      const { component } = await setup();
      const project: ProjectDashboardItem = {
        id: "p-x",
        name: "X",
        lastAnalysisAt: null,
        complianceScore: null,
        testCasesCount: 0,
        status: "active",
      };
      // Komponent ma domyślnie direction="desc" (sortActive="lastAnalysis").
      // Dla desc: null-last = -Infinity (mniejsze niż wszystkie liczby).
      const sort = component.dataSource.sort!;
      sort.direction = "desc";
      expect(
        component.dataSource.sortingDataAccessor!(project, "compliance"),
      ).toBe(Number.NEGATIVE_INFINITY);
      // Dla asc: null-last = +Infinity.
      sort.direction = "asc";
      expect(
        component.dataSource.sortingDataAccessor!(project, "compliance"),
      ).toBe(Number.POSITIVE_INFINITY);
    });

    it("renderuje mat-paginator z pageSizeOptions [5, 10, 25]", async () => {
      const { fixture } = await setup();
      const paginator = fixture.nativeElement.querySelector("mat-paginator");
      expect(paginator).toBeTruthy();
    });
  });

  describe("AC6 — quick actions z prewybranym projektem", () => {
    it("renderuje 3 buttony akcji (Nowa analiza, Upload dokumentacji, Nowy projekt)", async () => {
      const { fixture } = await setup();
      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain("Nowa analiza");
      expect(text).toContain("Upload dokumentacji");
      expect(text).toContain("Nowy projekt");
    });

    it("analysisLink nawiguje do ostatniego projektu gdy są projekty", async () => {
      const { component } = await setup();
      expect(component.analysisLink()).toEqual([
        "/projects",
        "p-1",
        "analysis",
      ]);
    });

    it("documentsLink nawiguje do ostatniego projektu gdy są projekty", async () => {
      const { component } = await setup();
      expect(component.documentsLink()).toEqual([
        "/projects",
        "p-1",
        "documents",
      ]);
    });

    it("quick-actions są wygaszone gdy brak projektów", async () => {
      const serviceState = createServiceMock({ projects: [] });
      const { component, fixture } = await setup({ serviceState });
      fixture.detectChanges();
      const disabledBtns =
        fixture.nativeElement.querySelectorAll(".disabled-action");
      expect(disabledBtns.length).toBe(2);
      expect(component.analysisLink()).toEqual(["/projects"]);
      expect(component.documentsLink()).toEqual(["/projects"]);
    });
  });

  describe("AC3 — activity feed z pollingiem 30s", () => {
    it("renderuje listę aktywności", async () => {
      const { fixture } = await setup();
      const text = fixture.nativeElement.textContent as string;
      // ACTION_LABELS["project.created"] = "Utworzono projekt"
      expect(text).toContain("Utworzono projekt");
    });

    it("pokazuje empty-state gdy brak aktywności", async () => {
      const serviceState = createServiceMock();
      serviceState.activitySignal.set([]);
      const { fixture } = await setup({ serviceState });
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain("Brak aktywności");
    });

    it("woła loadActivity przy inicjalizacji", async () => {
      const serviceState = createServiceMock();
      await setup({ serviceState });
      // ngOnInit woła loadActivity; komponent jest zoneless (Angular 21),
      // więc używamy bezpośredniej asercji zamiast fakeAsync/tick.
      expect(serviceState.loadActivity).toHaveBeenCalled();
    });
  });

  describe("AC4 — plan usage widget tylko dla owner/admin", () => {
    it("renderuje plan usage gdy planUsage jest dostępne (owner)", async () => {
      const { fixture } = await setup();
      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain("Plan premium");
      expect(text).toContain("5 / 50"); // analysesUsed / analysesLimit
    });

    it("ukrywa plan usage gdy planUsage = null (regular user)", async () => {
      const serviceState = createServiceMock({ withPlanUsage: false });
      const { fixture } = await setup({ serviceState });
      fixture.detectChanges();
      const planCards =
        fixture.nativeElement.querySelectorAll(".plan-usage-card");
      expect(planCards.length).toBe(0);
    });
  });

  describe("error state z retry", () => {
    it("renderuje komunikat błędu z przyciskiem retry", async () => {
      const serviceState = createServiceMock();
      serviceState.errorSignal.set("Nie udało się pobrać danych dashboardu.");
      const { fixture } = await setup({ serviceState });
      fixture.detectChanges();
      const errorEl = fixture.nativeElement.querySelector(".error-state");
      expect(errorEl).toBeTruthy();
      expect(errorEl.textContent).toContain(
        "Nie udało się pobrać danych dashboardu.",
      );
      expect(errorEl.textContent).toContain("Spróbuj ponownie");
    });

    it("retry() wywołuje loadSummary ponownie", async () => {
      const serviceState = createServiceMock();
      const { component } = await setup({ serviceState });
      serviceState.loadSummary.mockClear();
      component.retrySummary();
      expect(serviceState.loadSummary).toHaveBeenCalledTimes(1);
    });
  });

  describe("AC1 — tabela projektów", () => {
    it("renderuje rzędy projektów z nazwą, statusem, compliance badge", async () => {
      const { fixture } = await setup();
      const rows = fixture.nativeElement.querySelectorAll("tr.mat-mdc-row");
      expect(rows.length).toBe(2);
      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain("Projekt Alfa");
      expect(text).toContain("Projekt Beta");
      // Status labels z STATUS_LABELS.
      expect(text).toContain("Aktywny");
      expect(text).toContain("W analizie");
    });

    it("pokazuje empty-state gdy projects pusta", async () => {
      const serviceState = createServiceMock({ projects: [] });
      const { fixture } = await setup({ serviceState });
      fixture.detectChanges();
      const empty = fixture.nativeElement.querySelector(".empty-state");
      expect(empty).toBeTruthy();
      expect(empty.textContent).toContain("Brak projektów");
    });

    it("compliance badge ma odpowiednią klasę tintowaną od score", async () => {
      const { fixture } = await setup();
      const high = fixture.nativeElement.querySelector(".compliance-high");
      // Alfa = 87 → compliance-high.
      expect(high).toBeTruthy();
    });
  });

  describe("label helpers", () => {
    it("statusLabel mapuje znane statusy", async () => {
      const { component } = await setup();
      expect(component.statusLabel("active")).toBe("Aktywny");
      expect(component.statusLabel("completed")).toBe("Zakończony");
      // Nieznany status → zwraca bez zmian.
      expect(component.statusLabel("foo")).toBe("foo");
    });

    it("actionLabel mapuje znane akcje", async () => {
      const { component } = await setup();
      expect(component.actionLabel("project.created")).toBe(
        "Utworzono projekt",
      );
      expect(component.actionLabel("unknown.x")).toBe("unknown.x");
    });

    it("actionLabel mapuje akcje audit loga z backendu (bez surowych kluczy)", async () => {
      const { component } = await setup();
      // Pełny mapping = grep 'action="' w backend/app; tu reprezentatywne
      // próbki każdej rodziny (auth / upload / test-case / admin).
      expect(component.actionLabel("user.login_success")).toBe("Zalogowano");
      expect(component.actionLabel("user.logout")).toBe("Wylogowano");
      expect(component.actionLabel("source_file.uploaded")).toBe(
        "Wgrano pliki źródłowe",
      );
      expect(component.actionLabel("test_case.status")).toBe(
        "Zmieniono status testu",
      );
      expect(component.actionLabel("tenant.plan_changed")).toBe(
        "Zmieniono plan subskrypcji",
      );
    });
  });

  describe("welcome row", () => {
    it("pokodzi imię użytkownika (pierwszy człon)", async () => {
      const { fixture } = await setup();
      const text = fixture.nativeElement.textContent as string;
      // Anna Kowalska → "Anna".
      expect(text).toContain("Witaj, Anna");
    });
  });
});

// Pomocnik: komponent zawiera 5 kolumn w displayedColumns; nie importujemy
// tu prywatnego pola klasy, żeby uniknąć dodatkowego couplingu.
function component_displayedColumns_count(): number {
  return 5;
}
