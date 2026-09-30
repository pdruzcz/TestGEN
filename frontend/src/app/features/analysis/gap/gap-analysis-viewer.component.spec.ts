import { provideHttpClient, withInterceptors } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { provideAnimationsAsync } from "@angular/platform-browser/animations/async";
import { ActivatedRoute } from "@angular/router";

import { snakeCaseInterceptor } from "../../../core/interceptors/snake-case.interceptor";
import { GapAnalysisViewerComponent } from "./gap-analysis-viewer.component";

const apiUrl = "/api/v1";

function routeStub(documentId: string, projectId = "p1"): ActivatedRoute {
  return {
    snapshot: {
      paramMap: {
        get: (key: string) => (key === "projectId" ? projectId : null),
      },
      queryParamMap: {
        get: (key: string) => (key === "documentId" ? documentId : null),
      },
      queryParams: { documentId },
    },
  } as unknown as ActivatedRoute;
}

function gapItem(overrides: Record<string, unknown> = {}) {
  return {
    requirement_id: "FR-001",
    requirement_text:
      "Użytkownik musi móc zalogować się do systemu podając login i hasło.",
    status: "implemented",
    mapped_entities: ["LoginService.authenticate", "UserController.login"],
    issue_description: null,
    confidence: 0.95,
    ...overrides,
  };
}

function gapAnalysisPayload(items: Record<string, unknown>[]) {
  return {
    summary: {
      total_requirements: items.length,
      implemented: items.filter((i) => i["status"] === "implemented").length,
      not_implemented: items.filter((i) => i["status"] === "not_implemented")
        .length,
      partial: items.filter((i) => i["status"] === "partial").length,
      divergent: items.filter((i) => i["status"] === "divergent").length,
      coverage_percentage: 62.5,
      critical_gaps: ["FR-003"],
    },
    items,
  };
}

function flushAnalysis(
  httpMock: HttpTestingController,
  documentId = "doc-1",
  items: Record<string, unknown>[] = [gapItem()],
  filename = "spec.pdf",
) {
  const req = httpMock.expectOne(`${apiUrl}/documents/${documentId}/analysis`);
  expect(req.request.method).toBe("GET");
  req.flush({
    document_id: documentId,
    filename,
    mode: "native",
    classification: null,
    requirements: null,
    glossary: null,
    inconsistencies: null,
    gap_analysis: gapAnalysisPayload(items),
    traceability: null,
    test_generation: null,
  });
  return req;
}

describe("GapAnalysisViewerComponent", () => {
  let httpMock: HttpTestingController;

  async function createComponent(documentId = "doc-1") {
    await TestBed.configureTestingModule({
      imports: [GapAnalysisViewerComponent],
      providers: [
        provideRouter([]),
        // Interceptor jak w runtime: odpowiedzi snake_case → camelCase
        // (gap_analysis → gapAnalysis itd.).
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub(documentId) },
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(GapAnalysisViewerComponent);
    fixture.detectChanges(); // triggers ngOnInit → GET
    return fixture;
  }

  afterEach(() => {
    httpMock
      .match(() => true)
      .forEach((r) => {
        try {
          r.flush({});
        } catch {
          // already resolved
        }
      });
  });

  it("loads summary + items from persistence and renders them (AC3)", async () => {
    const fixture = await createComponent();
    flushAnalysis(httpMock, "doc-1", [
      gapItem({ requirement_id: "FR-001", status: "implemented" }),
      gapItem({
        requirement_id: "FR-003",
        status: "not_implemented",
        requirement_text:
          "Użytkownik musi móc utworzyć nowe zamówienie (krytyczne).",
        mapped_entities: [],
        issue_description: "Brak implementacji dla wymagania 'FR-003'",
        confidence: 0,
      }),
    ]);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.analysisResults().length).toBe(2);
    expect(component.coverageSummary()?.coveragePercentage).toBe(62.5);
    expect(component.coverageSummary()?.criticalGaps).toEqual(["FR-003"]);

    const text = fixture.nativeElement.textContent;
    // requirement ids + text
    expect(text).toContain("FR-001");
    expect(text).toContain("FR-003");
    expect(text).toContain("zalogować się do systemu");
    // status chips
    expect(text).toContain("Zaimplementowane");
    expect(text).toContain("Brak implementacji");
    // coverage summary card
    expect(text).toContain("Całkowite pokrycie");
    expect(text).toContain("62.5%");
    // mapped entities block (implemented item has entities)
    expect(text).toContain("Zmapowane encje");
    expect(text).toContain("LoginService.authenticate");
  });

  it("filters items by status (AC3)", async () => {
    const fixture = await createComponent();
    flushAnalysis(httpMock, "doc-1", [
      gapItem({ requirement_id: "FR-1", status: "implemented" }),
      gapItem({ requirement_id: "FR-3", status: "not_implemented" }),
    ]);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.filteredResults().length).toBe(2);

    component.selectedStatus.set("not_implemented");
    fixture.detectChanges();

    expect(component.filteredResults().length).toBe(1);
    expect(component.filteredResults()[0].requirementId).toBe("FR-3");
  });

  it("handles a missing gap_analysis payload gracefully (AC3)", async () => {
    const fixture = await createComponent();
    const req = httpMock.expectOne(`${apiUrl}/documents/doc-1/analysis`);
    req.flush({
      document_id: "doc-1",
      filename: "spec.pdf",
      gap_analysis: null,
    });
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.analysisResults().length).toBe(0);
    expect(component.coverageSummary()?.coveragePercentage).toBe(0);
    expect(component.isLoading()).toBe(false);
  });

  it("does not fetch analysis when no document id is provided (project view)", async () => {
    await TestBed.configureTestingModule({
      imports: [GapAnalysisViewerComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub("") },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(GapAnalysisViewerComponent);
    fixture.detectChanges();

    const listReq = httpMock.expectOne(
      `${apiUrl}/projects/p1/documents?page=1&page_size=100`,
    );
    expect(listReq.request.method).toBe("GET");
    listReq.flush([]);
    fixture.detectChanges();

    expect(fixture.componentInstance.documentId()).toBe("");
    httpMock.expectNone(`${apiUrl}/documents//analysis`);
  });
});
