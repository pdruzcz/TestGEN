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
import { GlossaryListComponent } from "./glossary-list.component";

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

function termItem(overrides: Record<string, unknown> = {}) {
  return {
    document_id: "doc-1",
    term: "API",
    definition: "Aplikacyjny interfejs programistyczny.",
    occurrences_count: 8,
    term_type: "acronym",
    source_sections: [{ section_id: "g", title: "Glosariusz" }],
    is_verified: false,
    code_mappings: [
      {
        name: "ApiController",
        type: "class",
        similarity: 1.0,
        is_confirmed: false,
      },
    ],
    ...overrides,
  };
}

function flushList(
  httpMock: HttpTestingController,
  documentId = "doc-1",
  terms: Record<string, unknown>[] = [termItem()],
  filename = "spec.pdf",
) {
  const req = httpMock.expectOne(`${apiUrl}/documents/${documentId}/glossary`);
  expect(req.request.method).toBe("GET");
  req.flush({
    document_id: documentId,
    filename,
    total: terms.length,
    terms,
  });
  return req;
}

describe("GlossaryListComponent", () => {
  let httpMock: HttpTestingController;

  async function createComponent(documentId = "doc-1") {
    await TestBed.configureTestingModule({
      imports: [GlossaryListComponent],
      providers: [
        provideRouter([]),
        // Interceptor jak w runtime: odpowiedzi snake_case → camelCase,
        // ciała żądań camelCase → snake_case.
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub(documentId) },
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(GlossaryListComponent);
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

  it("loads and renders terms on init", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.terms().length).toBe(1);
    expect(component.terms()[0].term).toBe("API");

    const text = fixture.nativeElement.textContent;
    expect(text).toContain("API");
    expect(text).toContain("Aplikacyjny interfejs programistyczny.");
    expect(text).toContain("Akronim");
    expect(text).toContain("8 wystąpień");
  });

  it("renders code mappings with similarity and type tag", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain("ApiController");
    expect(text).toContain("klasa");
    expect(text).toContain("100%");
  });

  it("opens inline edit mode and saves the definition via PUT", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const editBtn = fixture.nativeElement.querySelector(
      '[title="Edytuj definicję"]',
    ) as HTMLButtonElement;
    editBtn.click();
    fixture.detectChanges();

    expect(
      fixture.nativeElement.querySelector('[title="Zapisz zmiany"]'),
    ).toBeTruthy();

    const component = fixture.componentInstance;
    component.editDefinitionText.set("Nowa definicja API.");
    fixture.detectChanges();

    fixture.nativeElement.querySelector('[title="Zapisz zmiany"]').click();

    const putReq = httpMock.expectOne(`${apiUrl}/documents/doc-1/glossary/API`);
    expect(putReq.request.method).toBe("PUT");
    expect(putReq.request.body).toEqual({ definition: "Nowa definicja API." });
    putReq.flush(termItem({ definition: "Nowa definicja API." }));

    // reload GET after save
    flushList(httpMock, "doc-1", [
      termItem({ definition: "Nowa definicja API." }),
    ]);
    fixture.detectChanges();

    expect(component.editingTerm()).toBeNull();
    expect(fixture.nativeElement.textContent).toContain("Nowa definicja API.");
  });

  it("confirms a code mapping via PUT (confirmed_mapping_ids) and reloads", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    const term = component.terms()[0];
    const mapping = term.codeMappings[0];
    component.toggleMapping(term, mapping, true);

    const putReq = httpMock.expectOne(`${apiUrl}/documents/doc-1/glossary/API`);
    expect(putReq.request.method).toBe("PUT");
    expect(putReq.request.body).toEqual({
      confirmed_mapping_ids: ["ApiController"],
    });
    putReq.flush(termItem());

    flushList(httpMock);
    fixture.detectChanges();
  });

  it("maps glossary to code via POST and updates the list", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const buttons: HTMLButtonElement[] = Array.from(
      fixture.nativeElement.querySelectorAll("button"),
    );
    const mapBtn = buttons.find((b) =>
      (b.textContent || "").includes("Mapuj na kod"),
    ) as HTMLButtonElement;
    expect(mapBtn).toBeTruthy();
    mapBtn.click();

    const postReq = httpMock.expectOne(
      `${apiUrl}/documents/doc-1/glossary/map-to-code`,
    );
    expect(postReq.request.method).toBe("POST");
    postReq.flush({
      document_id: "doc-1",
      filename: "spec.pdf",
      total: 1,
      terms: [
        termItem({
          code_mappings: [
            {
              name: "ApiController",
              type: "class",
              similarity: 1.0,
              is_confirmed: false,
            },
          ],
        }),
      ],
    });
    fixture.detectChanges();

    expect(fixture.componentInstance.isMapping()).toBeFalsy();
    expect(fixture.nativeElement.textContent).toContain("ApiController");
  });

  it("shows empty state when no document id is provided", async () => {
    await TestBed.configureTestingModule({
      imports: [GlossaryListComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub("") },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(GlossaryListComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.documentId()).toBe("");
    expect(fixture.componentInstance.terms().length).toBe(0);
    // no GET issued without a document id
    httpMock.expectNone(`${apiUrl}/documents//glossary`);
  });
});
