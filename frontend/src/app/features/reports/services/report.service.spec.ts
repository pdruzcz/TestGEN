import { TestBed } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { signal } from "@angular/core";
import { of, throwError } from "rxjs";
import { environment } from "../../../../environments/environment";
import { GapAnalysisService } from "../../gap-analysis/services/gap-analysis.service";
import { SecurityScanService } from "../../projects/security/services/security-scan.service";
import { TestCaseService } from "../../test-cases/services/test-case.service";
import {
  ReportData,
  ReportKpis,
  ReportService,
  buildConclusions,
} from "./report.service";

const PROJECT_ID = "p1";
const API = environment.apiUrl;

function makeKpis(overrides: Partial<ReportKpis> = {}): ReportKpis {
  return {
    complianceScore: null,
    coveragePercentage: null,
    totalFindings: 0,
    criticalCount: 0,
    highCount: 0,
    mediumCount: 0,
    lowCount: 0,
    testCasesTotal: 0,
    testCasesReady: 0,
    testCasesPassed: 0,
    ...overrides,
  };
}

describe("buildConclusions (AC4)", () => {
  it("describes compliance level in plain Polish", () => {
    const conclusions = buildConclusions(
      makeKpis({ complianceScore: 85 }),
      [],
    );
    expect(conclusions[0]).toContain("85%");
    expect(conclusions[0]).toContain("dobry");
  });

  it("warns about critical findings first", () => {
    const conclusions = buildConclusions(
      makeKpis({ totalFindings: 3, criticalCount: 2, highCount: 1 }),
      [],
    );
    expect(conclusions.some((c) => c.includes("2 problemów o znaczeniu krytycznym"))).toBe(true);
  });

  it("reports improving trend", () => {
    const conclusions = buildConclusions(makeKpis(), [
      { score: 40 } as never,
      { score: 70 } as never,
    ]);
    expect(conclusions.some((c) => c.includes("wzrósł o 30"))).toBe(true);
  });

  it("contains no technical jargon (CWE/CVE)", () => {
    const conclusions = buildConclusions(
      makeKpis({ complianceScore: 30, totalFindings: 5, criticalCount: 1 }),
      [],
    );
    for (const c of conclusions) {
      expect(c).not.toContain("CWE");
      expect(c).not.toContain("CVE");
    }
  });
});

describe("ReportService", () => {
  let service: ReportService;
  let httpMock: HttpTestingController;

  const securityResponse = {
    findings: [
      {
        id: "sf1",
        vulnerabilityType: "SQL Injection",
        description: "opis",
        severity: "critical",
        cweId: "CWE-89",
        cvssScore: 9.8,
        filePath: "app/db.py",
        lineStart: 10,
        codeSnippet: "cursor.execute(q)",
        recommendation: "Użyj parametrów.",
      },
    ],
    total: 1,
    page: 1,
    pageSize: 200,
  };

  const securityMock = {
    listFindings: vi.fn(),
  };

  const gapMock = {
    getFindings: vi.fn().mockReturnValue(
      of({
        findings: [
          {
            id: "gf1",
            gapType: "missing",
            description: "Brak walidacji",
            severity: "medium",
            requirementText: "System waliduje dane.",
            codeReference: "app/forms.py",
            skeletonCode: null,
            skeletonLanguage: null,
          },
        ],
      }),
    ),
    getSummary: vi.fn().mockReturnValue(of({ coveragePercentage: 72 })),
    getTrend: vi.fn().mockReturnValue(
      of({
        points: [
          { label: "#1", score: 50 },
          { label: "#2", score: 80 },
        ],
      }),
    ),
  };

  const testCaseMock = {
    list: vi.fn().mockReturnValue(
      of({ items: [], total: 5, statusCounts: {} }),
    ),
    totalSignal: signal(5),
    statusCountsSignal: signal({
      ready: 2,
      passed: 1,
      failed: 0,
      skipped: 0,
      draft: 2,
    }),
  };

  // Aplikacja jest zoneless (brak zone.js), więc fakeAsync/tick nie działa —
  // opóźnieniami etapów generowania raportu sterują fake timery vitest.
  beforeEach(() => {
    vi.useFakeTimers();
    securityMock.listFindings.mockReturnValue(of(securityResponse));
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: SecurityScanService, useValue: securityMock },
        { provide: GapAnalysisService, useValue: gapMock },
        { provide: TestCaseService, useValue: testCaseMock },
      ],
    });
    service = TestBed.inject(ReportService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    vi.useRealTimers();
  });

  function flushDirectRequests(): void {
    httpMock
      .expectOne(`${API}/projects/${PROJECT_ID}/compliance`)
      .flush({ score: 65, totalFindings: 2, breakdown: {} });
    httpMock
      .expectOne(`${API}/projects/${PROJECT_ID}/compliance/modules`)
      .flush([
        { filePath: "app/db.py", score: 40, totalFindings: 1, breakdown: {} },
      ]);
  }

  it("generates a report through all stages (AC7) and merges findings", () => {
    let result: ReportData | undefined;
    service
      .generateReport(PROJECT_ID, "both")
      .subscribe((data) => (result = data));

    expect(service.reportStatusSignal()).toBe("generating");
    flushDirectRequests();
    vi.advanceTimersByTime(250); // treść
    vi.advanceTimersByTime(250); // render

    expect(result).toBeDefined();
    expect(service.reportStatusSignal()).toBe("done");
    expect(service.reportStageSignal()).toBe(3);

    // Ustalenia z obu źródeł, posortowane wg severity.
    expect(result!.findings.length).toBe(2);
    expect(result!.findings[0].source).toBe("security");
    expect(result!.findings[0].severity).toBe("critical");
    expect(result!.findings[0].cweId).toBe("CWE-89");
    expect(result!.findings[1].source).toBe("gap");

    // KPI z realnych endpointów.
    expect(result!.kpis.complianceScore).toBe(65);
    expect(result!.kpis.coveragePercentage).toBe(72);
    expect(result!.kpis.testCasesTotal).toBe(5);
    expect(result!.kpis.testCasesReady).toBe(2);

    expect(result!.trendPoints.length).toBe(2);
    expect(result!.conclusions.length).toBeGreaterThan(0);
    expect(service.reportDataSignal()).toEqual(result!);
  });

  it("continues best-effort when a single source fails", () => {
    securityMock.listFindings.mockReturnValue(
      throwError(() => new Error("boom")),
    );

    let result: ReportData | undefined;
    service
      .generateReport(PROJECT_ID, "executive")
      .subscribe((data) => (result = data));

    flushDirectRequests();
    vi.advanceTimersByTime(500);

    expect(result).toBeDefined();
    expect(result!.findings.length).toBe(1);
    expect(result!.findings[0].source).toBe("gap");
    expect(service.reportStatusSignal()).toBe("done");
  });

  it("reset() clears state", () => {
    service.generateReport(PROJECT_ID, "executive").subscribe();
    flushDirectRequests();
    vi.advanceTimersByTime(500);

    service.reset();
    expect(service.reportStatusSignal()).toBe("idle");
    expect(service.reportStageSignal()).toBe(0);
    expect(service.reportDataSignal()).toBeNull();
  });
});
