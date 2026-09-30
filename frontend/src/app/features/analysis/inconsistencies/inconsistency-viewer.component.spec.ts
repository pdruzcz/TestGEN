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
import { InconsistencyViewerComponent } from "./inconsistency-viewer.component";

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

function incItem(overrides: Record<string, unknown> = {}) {
  return {
    inconsistency_id: "inc-1",
    type: "contradiction",
    severity: "critical",
    description:
      "Wymaganie FR-1 mówi, że system musi obsługiwać logowanie, a FR-2 — że nie może.",
    affected_requirements: ["FR-1", "FR-2"],
    suggestion: "Rozważ zmodyfikowanie jednego z wymagań.",
    source_section_id: "s1",
    status: "open",
    ...overrides,
  };
}

function flushList(
  httpMock: HttpTestingController,
  documentId = "doc-1",
  inconsistencies: Record<string, unknown>[] = [incItem()],
  filename = "spec.pdf",
) {
  const req = httpMock.expectOne(
    `${apiUrl}/documents/${documentId}/inconsistencies`,
  );
  expect(req.request.method).toBe("GET");
  req.flush({
    document_id: documentId,
    filename,
    total: inconsistencies.length,
    inconsistencies,
  });
  return req;
}

describe("InconsistencyViewerComponent", () => {
  let httpMock: HttpTestingController;

  async function createComponent(documentId = "doc-1") {
    await TestBed.configureTestingModule({
      imports: [InconsistencyViewerComponent],
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
    const fixture = TestBed.createComponent(InconsistencyViewerComponent);
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

  it("loads and renders inconsistencies on init (AC4)", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.inconsistencies().length).toBe(1);
    expect(component.inconsistencies()[0].inconsistencyId).toBe("inc-1");

    // expand the panel so its body renders
    (
      fixture.nativeElement.querySelector(
        "mat-expansion-panel-header",
      ) as HTMLElement
    ).click();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain(
      "Wymaganie FR-1 mówi, że system musi obsługiwać logowanie",
    );
    expect(text).toContain("Krytyczny"); // severity chip
    expect(text).toContain("Otwarte"); // status chip
    expect(text).toContain("FR-1"); // affected requirement
    expect(text).toContain("Rozważ zmodyfikowanie jednego z wymagań.");
  });

  it("changes status via PUT and updates the chip (AC4)", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    // expand panel to reveal the status action buttons
    (
      fixture.nativeElement.querySelector(
        "mat-expansion-panel-header",
      ) as HTMLElement
    ).click();
    fixture.detectChanges();

    const acceptBtn = fixture.nativeElement.querySelector(
      '[title="Akceptuj"]',
    ) as HTMLButtonElement;
    expect(acceptBtn).toBeTruthy();
    acceptBtn.click();

    const putReq = httpMock.expectOne(
      `${apiUrl}/documents/doc-1/inconsistencies/inc-1`,
    );
    expect(putReq.request.method).toBe("PUT");
    expect(putReq.request.body).toEqual({ status: "accepted" });
    putReq.flush(incItem({ status: "accepted" }));
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.inconsistencies()[0].status).toBe("accepted");
    expect(component.acceptedCount()).toBe(1);
    expect(fixture.nativeElement.textContent).toContain("Zaakceptowane");
  });

  it("filters inconsistencies by status (AC4)", async () => {
    const fixture = await createComponent();
    flushList(httpMock, "doc-1", [
      incItem({ inconsistency_id: "inc-open", status: "open" }),
      incItem({ inconsistency_id: "inc-fixed", status: "fixed" }),
    ]);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.inconsistencies().length).toBe(2);
    expect(component.filteredInconsistencies().length).toBe(2);

    component.selectedStatus.set("fixed");
    fixture.detectChanges();

    expect(component.filteredInconsistencies().length).toBe(1);
    expect(component.filteredInconsistencies()[0].inconsistencyId).toBe(
      "inc-fixed",
    );
  });

  it("loads the project-wide list when no document id is provided — UI bug fix", async () => {
    // Wcześniej ngOnInit nie wołał loadProjectInconsistencies — widok
    // projektu był pusty mimo istniejącego endpointu agregującego.
    await TestBed.configureTestingModule({
      imports: [InconsistencyViewerComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub("") },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(InconsistencyViewerComponent);
    fixture.detectChanges();

    const req = httpMock.expectOne(`${apiUrl}/projects/p1/inconsistencies`);
    expect(req.request.method).toBe("GET");
    req.flush({
      project_id: "p1",
      documents: 1,
      total: 1,
      inconsistencies: [
        incItem({ document_id: "doc-9", document_filename: "spec.pdf" }),
      ],
    });
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.isProjectView()).toBe(true);
    expect(component.inconsistencies().length).toBe(1);
    // plik dokumentu źródłowego widoczny przy wierszu (widok projektu)
    expect(fixture.nativeElement.textContent).toContain("spec.pdf");
    httpMock.expectNone(`${apiUrl}/documents//inconsistencies`);
  });
});
