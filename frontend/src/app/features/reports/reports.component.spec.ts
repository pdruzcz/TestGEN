import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute, provideRouter } from "@angular/router";
import { provideHttpClient } from "@angular/common/http";
import { provideHttpClientTesting } from "@angular/common/http/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { signal } from "@angular/core";
import { of } from "rxjs";
import { ReportsComponent } from "./reports.component";
import {
  REPORT_STAGES,
  ReportData,
  ReportService,
} from "./services/report.service";

const PROJECT_ID = "p1";

function routeStub(projectId: string): Partial<ActivatedRoute> {
  return {
    snapshot: {
      paramMap: { get: () => projectId },
    } as unknown as ActivatedRoute["snapshot"],
  };
}

function makeReportData(): ReportData {
  return {
    projectId: PROJECT_ID,
    generatedAt: new Date().toISOString(),
    kpis: {
      complianceScore: 70,
      coveragePercentage: 60,
      totalFindings: 1,
      criticalCount: 0,
      highCount: 1,
      mediumCount: 0,
      lowCount: 0,
      testCasesTotal: 3,
      testCasesReady: 1,
      testCasesPassed: 1,
    },
    severityCounts: { critical: 0, high: 1, medium: 0, low: 0 },
    moduleScores: [],
    trendPoints: [],
    conclusions: ["Wniosek testowy."],
    findings: [],
  };
}

describe("ReportsComponent", () => {
  let fixture: ComponentFixture<ReportsComponent>;
  let component: ReportsComponent;

  const reportServiceMock = {
    reportTypeSignal: signal<"executive" | "technical" | "both">("executive"),
    reportStatusSignal: signal<"idle" | "generating" | "done" | "error">(
      "idle",
    ),
    reportStageSignal: signal(0),
    reportDataSignal: signal<ReportData | null>(null),
    generateReport: vi.fn(),
    reset: vi.fn(),
  };

  beforeEach(async () => {
    reportServiceMock.reportStatusSignal.set("idle");
    reportServiceMock.reportStageSignal.set(0);
    reportServiceMock.reportDataSignal.set(null);
    reportServiceMock.generateReport.mockReturnValue(of(makeReportData()));
    reportServiceMock.reset.mockClear();

    await TestBed.configureTestingModule({
      imports: [ReportsComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        { provide: ReportService, useValue: reportServiceMock },
        { provide: ActivatedRoute, useValue: routeStub(PROJECT_ID) },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ReportsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("renders report type options (AC1)", () => {
    const el: HTMLElement = fixture.nativeElement;
    const radios = el.querySelectorAll("mat-radio-button");
    expect(radios.length).toBe(3);
    expect(el.textContent).toContain("Podsumowanie wykonawcze");
    expect(el.textContent).toContain("Szczegóły techniczne");
    expect(el.textContent).toContain("Oba raporty");
  });

  it("resets report state on init", () => {
    expect(reportServiceMock.reset).toHaveBeenCalled();
  });

  it("starts generation with selected type", () => {
    component.selectedType = "both";
    component.generate();
    expect(reportServiceMock.generateReport).toHaveBeenCalledWith(
      PROJECT_ID,
      "both",
    );
  });

  it("shows progress stages while generating (AC7)", () => {
    reportServiceMock.reportStatusSignal.set("generating");
    reportServiceMock.reportStageSignal.set(1);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector("mat-progress-bar")).toBeTruthy();
    expect(el.textContent).toContain(`Etap 2/${REPORT_STAGES.length}`);
    expect(el.textContent).toContain("Analiza trendów");
  });

  it("shows the HTML preview when done (AC8)", () => {
    reportServiceMock.reportStatusSignal.set("done");
    reportServiceMock.reportDataSignal.set(makeReportData());
    reportServiceMock.reportTypeSignal.set("executive");
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector("app-report-preview")).toBeTruthy();
    expect(el.textContent).toContain("Wniosek testowy.");
  });

  it("shows an error message on failure", () => {
    reportServiceMock.reportStatusSignal.set("error");
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain(
      "Nie udało się wygenerować raportu",
    );
  });
});
