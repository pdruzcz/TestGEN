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
import { TraceabilityMatrixComponent } from "./traceability-matrix.component";

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

function traceEntry(overrides: Record<string, unknown> = {}) {
  return {
    requirement_id: "FR-1",
    requirement_text:
      "Użytkownik musi móc zalogować się do systemu podając login i hasło.",
    code_entities: ["LoginService.authenticate", "UserController.login"],
    test_cases: [],
    coverage_status: "partial",
    source_section_id: "s1",
    ...overrides,
  };
}

function tracePayload(entries: Record<string, unknown>[]) {
  return {
    document_name: "spec.pdf",
    total_requirements: entries.length,
    full_coverage: entries.filter((e) => e["coverage_status"] === "full")
      .length,
    partial_coverage: entries.filter((e) => e["coverage_status"] === "partial")
      .length,
    no_coverage: entries.filter((e) => e["coverage_status"] === "none").length,
    coverage_percentage: 50.0,
    entries,
  };
}

function flushAnalysis(
  httpMock: HttpTestingController,
  documentId = "doc-1",
  entries: Record<string, unknown>[] | null = null,
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
    gap_analysis: null,
    traceability: tracePayload(entries ?? [traceEntry()]),
    test_generation: null,
  });
  return req;
}

describe("TraceabilityMatrixComponent", () => {
  let httpMock: HttpTestingController;

  async function createComponent(documentId = "doc-1") {
    await TestBed.configureTestingModule({
      imports: [TraceabilityMatrixComponent],
      providers: [
        provideRouter([]),
        // Interceptor jak w runtime: odpowiedzi snake_case → camelCase.
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub(documentId) },
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(TraceabilityMatrixComponent);
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

  it("loads summary + entries from persistence and renders them (AC3)", async () => {
    const fixture = await createComponent();
    flushAnalysis(httpMock, "doc-1", [
      traceEntry({
        requirement_id: "FR-1",
        coverage_status: "partial",
        code_entities: ["LoginService"],
      }),
      traceEntry({
        requirement_id: "FR-3",
        coverage_status: "none",
        requirement_text: "System musi wspierać eksport do pliku CSV.",
        code_entities: [],
      }),
    ]);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.entries().length).toBe(2);
    expect(component.summary()?.partialCoverage).toBe(1);
    expect(component.summary()?.noCoverage).toBe(1);
    expect(component.summary()?.coveragePercentage).toBe(50);

    const text = fixture.nativeElement.textContent;
    // requirement ids + text
    expect(text).toContain("FR-1");
    expect(text).toContain("FR-3");
    expect(text).toContain("zalogować się do systemu");
    // status chips (PL labels)
    expect(text).toContain("Częściowe");
    expect(text).toContain("Brak");
    // coverage stat-cards
    expect(text).toContain("Pełne pokrycie");
    expect(text).toContain("Brak pokrycia");
    expect(text).toContain("Całkowite");
    // coverage badge percentage
    expect(text).toContain("50% pokrycia");
    // mapped code entity (partial entry; short name renders untruncated)
    expect(text).toContain("LoginService");
  });

  it("filters entries by search query (AC3)", async () => {
    const fixture = await createComponent();
    flushAnalysis(httpMock, "doc-1", [
      traceEntry({
        requirement_id: "FR-1",
        requirement_text: "funkcja login do uwierzytelniania",
      }),
      traceEntry({
        requirement_id: "FR-2",
        requirement_text: "System musi eksportować raport do pliku CSV.",
        code_entities: ["RaportExporter"],
      }),
    ]);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.filteredEntries().length).toBe(2);

    component.searchQuery.set("raport");
    fixture.detectChanges();

    expect(component.filteredEntries().length).toBe(1);
    expect(component.filteredEntries()[0].requirementId).toBe("FR-2");
  });

  it("handles a missing traceability payload gracefully (AC3)", async () => {
    const fixture = await createComponent();
    const req = httpMock.expectOne(`${apiUrl}/documents/doc-1/analysis`);
    req.flush({
      document_id: "doc-1",
      filename: "spec.pdf",
      traceability: null,
    });
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.entries().length).toBe(0);
    expect(component.summary()?.coveragePercentage).toBe(0);
    expect(component.isLoading()).toBe(false);
  });

  it("does not fetch analysis when no document id is provided (project view)", async () => {
    await TestBed.configureTestingModule({
      imports: [TraceabilityMatrixComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub("") },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(TraceabilityMatrixComponent);
    fixture.detectChanges();

    // Widok projektu: listuje dokumenty, ale nie odpyta /analysis per dokumnt
    // bez wyników listowania.
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
