import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { ActivatedRoute, provideRouter } from "@angular/router";
import { environment } from "../../../../environments/environment";
import { TestCase } from "../models/test-case.model";
import { TestCaseService } from "../services/test-case.service";
import { TestCasesManagementComponent } from "./test-cases-management.component";

const apiUrl = environment.apiUrl;

function routeStub(projectId: string) {
  return {
    snapshot: {
      paramMap: {
        get: (key: string) => (key === "projectId" ? projectId : null),
      },
    },
  };
}

function makeTc(overrides: Partial<TestCase> = {}): TestCase {
  return {
    id: "tc-1",
    tenantId: "t1",
    analysisResultId: "ar1",
    sourceFileId: null,
    title: "Test logowania",
    description: null,
    priority: "HIGH",
    type: "UNIT",
    framework: "PYTEST",
    status: "DRAFT",
    language: "python",
    testCode: null,
    imports: null,
    setupCode: null,
    teardownCode: null,
    preconditions: null,
    steps: null,
    expectedResult: null,
    testData: null,
    sourceFunction: "login",
    sourceClass: "AuthService",
    sourceEndpoint: null,
    scenarioDescription: null,
    scenarioRationale: null,
    edgeCaseDescription: null,
    confidenceScore: null,
    tags: null,
    isEdited: false,
    reviewedAt: null,
    reviewedBy: null,
    lastExecutedAt: null,
    lastExecutionResult: null,
    executionCount: 0,
    passCount: 0,
    failCount: 0,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

describe("TestCasesManagementComponent", () => {
  let fixture: ComponentFixture<TestCasesManagementComponent>;
  let component: TestCasesManagementComponent;
  let httpTesting: HttpTestingController;
  let service: TestCaseService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestCasesManagementComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: routeStub("p1") },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TestCasesManagementComponent);
    component = fixture.componentInstance;
    httpTesting = TestBed.inject(HttpTestingController);
    service = TestBed.inject(TestCaseService);
    fixture.detectChanges();
  });

  // Świadomie bez sprzątania zaległych żądań przez flush(404) — subskrypcje
  // komponentu nie mają handlera błędu, więc vitest raportowałby to jako
  // uncaught exception. Niezakończone żądania znikają wraz z TestBed.

  it("should create and load test cases on init", () => {
    expect(component).toBeTruthy();
    const reqs = httpTesting.match((req) =>
      req.url.startsWith(`${apiUrl}/test-cases`),
    );
    expect(reqs.length).toBe(1);
  });

  it("filters by priority/status client-side (AC2)", () => {
    service.testCasesSignal.set([
      makeTc({ id: "1", priority: "HIGH", status: "DRAFT" }),
      makeTc({ id: "2", priority: "LOW", status: "READY" }),
    ]);
    component.onFiltersChange({
      priorities: ["HIGH"],
      types: [],
      statuses: [],
      modules: [],
    });
    expect(component.filteredTestCases().length).toBe(1);
    expect(component.filteredTestCases()[0].id).toBe("1");

    component.onFiltersChange({
      priorities: [],
      types: [],
      statuses: ["READY"],
      modules: [],
    });
    expect(component.filteredTestCases()[0].id).toBe("2");
  });

  it("groups by module with expand/collapse (AC3)", () => {
    service.testCasesSignal.set([
      makeTc({ id: "1", sourceClass: "AuthService" }),
      makeTc({ id: "2", sourceClass: "UserService" }),
      makeTc({ id: "3", sourceClass: "AuthService" }),
    ]);
    component.onGroupByChange("module");
    const groups = component.groups();
    expect(groups.length).toBe(2);
    expect(groups.find((g) => g.key === "AuthService")?.items.length).toBe(2);

    component.toggleGroup("AuthService");
    expect(component.isGroupCollapsed("AuthService")).toBe(true);
    component.toggleGroup("AuthService");
    expect(component.isGroupCollapsed("AuthService")).toBe(false);
  });

  it("toggles row selection and select-all (AC5)", () => {
    service.testCasesSignal.set([makeTc({ id: "1" }), makeTc({ id: "2" })]);
    component.toggleSelection("1");
    expect(component.selectedCount()).toBe(1);
    expect(component.isSelected("1")).toBe(true);

    component.toggleSelectAll();
    expect(component.selectedCount()).toBe(2);
    expect(component.allVisibleSelected()).toBe(true);

    component.toggleSelectAll();
    expect(component.selectedCount()).toBe(0);
  });

  it("bulk status change calls the bulk-update endpoint (AC5)", () => {
    service.testCasesSignal.set([makeTc({ id: "1" })]);
    component.toggleSelection("1");
    component.bulkChangeStatus("READY");

    const req = httpTesting.expectOne(`${apiUrl}/test-cases/bulk-update`);
    expect(req.request.method).toBe("POST");
    expect(req.request.body.ids).toEqual(["1"]);
    expect(req.request.body.status).toBe("READY");
    req.flush({ affected: 1 });
    expect(component.selectedCount()).toBe(0);
  });

  it("cycles sort order and reloads (AC1)", () => {
    component.onSort("title");
    expect(component.sortBy()).toBe("title");
    expect(component.sortOrder()).toBe("asc");

    component.onSort("title");
    expect(component.sortOrder()).toBe("desc");
    expect(component.ariaSort("title")).toBe("descending");
  });

  it("keyboard: Space selects, Enter opens editor (AC8)", () => {
    const tc = makeTc({ id: "1" });
    service.testCasesSignal.set([tc]);

    const spaceEvent = new KeyboardEvent("keydown", { key: " " });
    component.onRowKeydown(spaceEvent, tc);
    expect(component.isSelected("1")).toBe(true);

    const enterEvent = new KeyboardEvent("keydown", { key: "Enter" });
    component.onRowKeydown(enterEvent, tc);
    expect(component.editingId()).toBe("1");
  });

  it("saving from the editor calls PUT and closes it (AC4)", () => {
    const tc = makeTc({ id: "1" });
    service.testCasesSignal.set([tc]);
    component.openEditor("1");
    component.saveTestCase("1", { title: "Nowy tytuł" });

    const req = httpTesting.expectOne(`${apiUrl}/test-cases/1`);
    expect(req.request.method).toBe("PUT");
    req.flush(makeTc({ id: "1", title: "Nowy tytuł" }));
    expect(component.editingId()).toBeNull();
  });

  describe("eksport do TestRail (Story 8.8)", () => {
    it("dialog podsumowuje zaznaczenie przed wysłaniem", () => {
      service.testCasesSignal.set([makeTc({ id: "1" }), makeTc({ id: "2" })]);
      component.toggleSelection("1");

      component.openTestRailExport();

      expect(component.isTestRailDialogOpen()).toBe(true);
      expect(component.testRailSummary()).toContain("1");
    });

    it("bez zaznaczenia zapowiada eksport całego projektu", () => {
      component.openTestRailExport();

      expect(component.testRailSummary()).toContain("wszystkie przypadki");
    });

    it("wysyła zaznaczone identyfikatory i pokazuje zadanie", () => {
      service.testCasesSignal.set([makeTc({ id: "1" })]);
      component.toggleSelection("1");
      component.openTestRailExport();

      component.confirmTestRailExport();

      const req = httpTesting.expectOne(
        (r) => r.url.endsWith("/export/testrail") && r.method === "POST",
      );
      expect(req.request.body.testCaseIds).toEqual(["1"]);
      req.flush({
        taskId: "celery-1",
        status: "pending",
        statusUrl: "/api/v1/tasks/celery-1",
        testCases: 1,
      });

      expect(component.testRailTaskId()).toBe("celery-1");
      expect(component.isExportingToTestRail()).toBe(false);
    });

    it("brak konfiguracji kieruje użytkownika do ustawień", () => {
      component.openTestRailExport();
      component.confirmTestRailExport();

      httpTesting
        .expectOne((r) => r.url.endsWith("/export/testrail"))
        .flush({ detail: "brak" }, { status: 404, statusText: "Not Found" });

      expect(component.testRailError()).toContain("nie jest skonfigurowana");
    });

    it("inny błąd pokazuje komunikat z backendu", () => {
      component.openTestRailExport();
      component.confirmTestRailExport();

      httpTesting
        .expectOne((r) => r.url.endsWith("/export/testrail"))
        .flush({ detail: "Kolejka niedostępna" }, { status: 503, statusText: "Unavailable" });

      expect(component.testRailError()).toBe("Kolejka niedostępna");
    });
  });

  describe("eksport do Jiry (Story 8.9)", () => {
    it("Xray idzie na własny endpoint", () => {
      service.testCasesSignal.set([makeTc({ id: "1" })]);
      component.toggleSelection("1");
      component.openExternalExport("xray");

      expect(component.exportTargetLabel()).toBe("Jira Xray");

      component.confirmTestRailExport();

      const req = httpTesting.expectOne(
        (r) => r.url.endsWith("/export/xray") && r.method === "POST",
      );
      expect(req.request.body.testCaseIds).toEqual(["1"]);
      req.flush({
        taskId: "celery-xray",
        status: "pending",
        statusUrl: "/api/v1/tasks/celery-xray",
        testCases: 1,
      });

      expect(component.testRailTaskId()).toBe("celery-xray");
    });

    it("Zephyr idzie na własny endpoint", () => {
      component.openExternalExport("zephyr");

      expect(component.exportTargetLabel()).toBe("Zephyr Scale");

      component.confirmTestRailExport();
      httpTesting
        .expectOne((r) => r.url.endsWith("/export/zephyr"))
        .flush({
          taskId: "celery-zephyr",
          status: "pending",
          statusUrl: "/api/v1/tasks/celery-zephyr",
          testCases: 0,
        });

      expect(component.testRailTaskId()).toBe("celery-zephyr");
    });

    it("komunikat o braku konfiguracji nazywa właściwy system", () => {
      component.openExternalExport("xray");
      component.confirmTestRailExport();

      httpTesting
        .expectOne((r) => r.url.endsWith("/export/xray"))
        .flush({ detail: "brak" }, { status: 404, statusText: "Not Found" });

      expect(component.testRailError()).toContain("Jira Xray");
    });

    it("przełączenie celu zmienia endpoint kolejnego eksportu", () => {
      component.openExternalExport("xray");
      component.closeTestRailExport();
      component.openTestRailExport();

      expect(component.exportTargetLabel()).toBe("TestRail");

      component.confirmTestRailExport();
      httpTesting
        .expectOne((r) => r.url.endsWith("/export/testrail"))
        .flush({
          taskId: "t",
          status: "pending",
          statusUrl: "/api/v1/tasks/t",
          testCases: 0,
        });
    });
  });

  describe("plakietka powiązania z TMS (Story 8.11)", () => {
    /** Tabela renderuje się dopiero po zakończeniu pierwszego pobrania. */
    function renderRows(testCases: TestCase[]): void {
      httpTesting
        .expectOne((r) => r.url.startsWith(`${apiUrl}/test-cases`))
        .flush({
          testCases,
          total: testCases.length,
          statusCounts: {
            ready: 0,
            passed: 0,
            failed: 0,
            skipped: 0,
            draft: testCases.length,
            disabled: 0,
          },
        });
      fixture.detectChanges();
    }

    it("pokazuje identyfikator przypadku po stronie TMS", () => {
      renderRows([makeTc({ tmsExternalId: "1234", tmsSyncedAt: "2026-09-25T10:00:00Z" })]);

      const badge: HTMLElement | null =
        fixture.nativeElement.querySelector(".tms-badge");
      expect(badge?.textContent).toContain("#1234");
    });

    it("przypadek bez powiązania nie dostaje plakietki", () => {
      renderRows([makeTc()]);

      expect(fixture.nativeElement.querySelector(".tms-badge")).toBeNull();
    });

    it("data synchronizacji siedzi w tooltipie, nie w kolumnie", () => {
      // Kolumna z kolejną datą rozpychałaby i tak szeroką tabelę.
      const title = component.tmsSyncTitle(
        makeTc({ tmsExternalId: "QA-7", tmsSyncedAt: "2026-09-25T10:00:00Z" }),
      );

      expect(title).toContain("QA-7");
      expect(title).toContain("ostatnia synchronizacja");
    });

    it("brak daty nie psuje opisu", () => {
      const title = component.tmsSyncTitle(
        makeTc({ tmsExternalId: "QA-7", tmsSyncedAt: null }),
      );

      expect(title).toContain("nieznana data");
    });
  });
});
