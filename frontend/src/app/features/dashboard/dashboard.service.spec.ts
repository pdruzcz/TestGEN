import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { environment } from "../../../environments/environment";
import { DashboardService } from "./dashboard.service";

const apiUrl = `${environment.apiUrl}/dashboard`;

describe("DashboardService", () => {
  let service: DashboardService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        DashboardService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(DashboardService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  describe("initial signal state", () => {
    it("should start with empty projects", () => {
      expect(service.projectsSignal()).toEqual([]);
    });

    it("should start with null statistics", () => {
      expect(service.statisticsSignal()).toBeNull();
    });

    it("should start with null planUsage", () => {
      expect(service.planUsageSignal()).toBeNull();
    });

    it("should start with empty activity", () => {
      expect(service.activitySignal()).toEqual([]);
    });

    it("should start with isLoading=false", () => {
      expect(service.isLoadingSummarySignal()).toBe(false);
      expect(service.isLoadingActivitySignal()).toBe(false);
    });
  });

  describe("loadSummary()", () => {
    it("should GET /dashboard/summary and update signals", () => {
      const summary = {
        projects: [
          {
            id: "p1",
            name: "Project A",
            lastAnalysisAt: "2026-07-15T10:00:00Z",
            complianceScore: 87.5,
            testCasesCount: 12,
            status: "active",
          },
        ],
        statistics: {
          totalProjects: 1,
          analysesThisMonth: 3,
          avgCompliance: 92.0,
          totalTestCases: 42,
          activeUsers: 5,
        },
        planUsage: {
          plan: "premium",
          analysesUsed: 3,
          analysesLimit: 50,
          projectsCount: 1,
        },
      };

      service.loadSummary().subscribe();
      const req = httpTesting.expectOne(`${apiUrl}/summary`);
      expect(req.request.method).toBe("GET");
      req.flush(summary);

      expect(service.projectsSignal().length).toBe(1);
      expect(service.projectsSignal()[0].name).toBe("Project A");
      expect(service.statisticsSignal()?.totalProjects).toBe(1);
      expect(service.planUsageSignal()?.plan).toBe("premium");
      expect(service.isLoadingSummarySignal()).toBe(false);
    });

    it("should clear isLoading on error", () => {
      service.loadSummary().subscribe({ error: () => undefined });
      const req = httpTesting.expectOne(`${apiUrl}/summary`);
      req.flush(null, { status: 500, statusText: "Server Error" });
      expect(service.isLoadingSummarySignal()).toBe(false);
      expect(service.errorSignal()).toContain("Nie udało się");
    });
  });

  describe("loadActivity()", () => {
    it("should GET /dashboard/audit-logs with limit param", () => {
      service.loadActivity(10).subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${apiUrl}/audit-logs`,
      );
      expect(req.request.method).toBe("GET");
      expect(req.request.params.get("limit")).toBe("10");
      req.flush({ items: [], total: 0 });
    });

    it("should default limit to 20", () => {
      service.loadActivity().subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${apiUrl}/audit-logs`,
      );
      expect(req.request.params.get("limit")).toBe("20");
      req.flush({ items: [], total: 0 });
    });

    it("should update activity signal with fetched entries", () => {
      const entries = [
        {
          id: "log1",
          userId: "u1",
          action: "project.created",
          resourceType: "project",
          resourceId: "p1",
          details: { name: "Project A" },
          createdAt: "2026-07-21T08:30:00Z",
          userEmail: "user@example.com",
        },
      ];

      service.loadActivity().subscribe();
      const req = httpTesting.expectOne(
        (r) => r.url === `${apiUrl}/audit-logs`,
      );
      req.flush({ items: entries, total: 1 });

      expect(service.activitySignal().length).toBe(1);
      expect(service.activitySignal()[0].action).toBe("project.created");
      expect(service.isLoadingActivitySignal()).toBe(false);
    });
  });
});
