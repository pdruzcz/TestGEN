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
import { RequirementListComponent } from "./requirement-list.component";

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

function reqItem(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    req_id: "REQ-1",
    text: "System musi wysyłać powiadomienia e-mail.",
    type: "functional",
    priority: "high",
    source_section_id: "sec-1",
    source_section_title: "Powiadomienia",
    confidence: 90,
    extraction_method: "native",
    status: "extracted",
    ...overrides,
  };
}

function flushList(
  httpMock: HttpTestingController,
  documentId = "doc-1",
  requirements: Record<string, unknown>[] = [reqItem()],
  filename = "spec.pdf",
) {
  const req = httpMock.expectOne(
    `${apiUrl}/documents/${documentId}/requirements`,
  );
  expect(req.request.method).toBe("GET");
  req.flush({
    document_id: documentId,
    filename,
    mode: "native",
    total: requirements.length,
    requirements,
  });
  return req;
}

describe("RequirementListComponent", () => {
  let httpMock: HttpTestingController;

  async function createComponent(documentId = "doc-1") {
    await TestBed.configureTestingModule({
      imports: [RequirementListComponent],
      providers: [
        provideRouter([]),
        // Interceptor jak w runtime: odpowiedzi snake_case → camelCase.
        // Bez niego speki mockują dane z pominięciem konwersji i przepuszczają
        // błędy „komponent czyta snake_case" niewidoczne w ng test.
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub(documentId) },
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(RequirementListComponent);
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

  it("loads and renders requirements on init", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    expect(component.requirements().length).toBe(1);
    expect(component.requirements()[0].req_id).toBe("REQ-1");
    expect(fixture.nativeElement.textContent).toContain(
      "System musi wysyłać powiadomienia e-mail.",
    );
  });

  it("renders the section title (not the section id) — UI bug fix", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain("Powiadomienia"); // source_section_title
  });

  it("shows a fallback label when section title and id are missing — UI bug fix", async () => {
    const fixture = await createComponent();
    flushList(httpMock, "doc-1", [
      reqItem({
        source_section_title: undefined,
        source_section_id: undefined,
      }),
    ]);
    fixture.detectChanges();

    // Przy ikonie lokalizacji nie może wisieć pusta etykieta.
    expect(fixture.nativeElement.textContent).toContain("Nieznana sekcja");
  });

  it("project view: Podgląd links to the requirement's own document — UI bug fix", async () => {
    const fixture = await createComponent(""); // bez documentId → widok projektu
    const listReq = httpMock.expectOne(`${apiUrl}/projects/p1/requirements`);
    expect(listReq.request.method).toBe("GET");
    listReq.flush({
      project_id: "p1",
      total: 1,
      documents: 1,
      requirements: [
        reqItem({ document_id: "doc-42", document_filename: "spec.pdf" }),
      ],
    });
    fixture.detectChanges();

    const link = fixture.nativeElement.querySelector(
      "a.view-link",
    ) as HTMLAnchorElement;
    expect(link).toBeTruthy();
    expect(link.getAttribute("href")).toContain(
      "/projects/p1/documents/doc-42",
    );
    expect(link.getAttribute("href")).toContain("highlight=sec-1");
  });

  it("accepts a requirement via API and reloads with accepted status", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const acceptBtn = fixture.nativeElement.querySelector(
      '[title="Akceptuj wymaganie"]',
    ) as HTMLButtonElement;
    expect(acceptBtn).toBeTruthy();
    acceptBtn.click();

    // POST /accept
    const postReq = httpMock.expectOne(
      `${apiUrl}/documents/doc-1/requirements/REQ-1/accept`,
    );
    expect(postReq.request.method).toBe("POST");
    postReq.flush(reqItem({ status: "accepted" }));

    // reload GET returns the accepted requirement
    flushList(httpMock, "doc-1", [reqItem({ status: "accepted" })]);
    fixture.detectChanges();

    expect(fixture.componentInstance.requirements()[0].status).toBe("accepted");
    expect(fixture.componentInstance.requirements()[0].accepted).toBe(true);
    expect(fixture.nativeElement.textContent).toContain("Zaakceptowane");
  });

  it("rejects a requirement via API and reloads with rejected status", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const rejectBtn = fixture.nativeElement.querySelector(
      '[title="Odrzuć wymaganie"]',
    ) as HTMLButtonElement;
    rejectBtn.click();

    const postReq = httpMock.expectOne(
      `${apiUrl}/documents/doc-1/requirements/REQ-1/reject`,
    );
    expect(postReq.request.method).toBe("POST");
    postReq.flush(reqItem({ status: "rejected" }));

    flushList(httpMock, "doc-1", [reqItem({ status: "rejected" })]);
    fixture.detectChanges();

    expect(fixture.componentInstance.requirements()[0].status).toBe("rejected");
    expect(fixture.nativeElement.textContent).toContain("Odrzucone");
  });

  it("undoes a decision via PUT (status=extracted) and reloads", async () => {
    const fixture = await createComponent();
    flushList(httpMock, "doc-1", [reqItem({ status: "accepted" })]);
    fixture.detectChanges();

    const undoBtn = fixture.nativeElement.querySelector(
      '[title="Cofnij decyzję"]',
    ) as HTMLButtonElement;
    expect(undoBtn).toBeTruthy();
    undoBtn.click();

    const putReq = httpMock.expectOne(
      `${apiUrl}/documents/doc-1/requirements/REQ-1`,
    );
    expect(putReq.request.method).toBe("PUT");
    expect(putReq.request.body).toEqual({ status: "extracted" });
    putReq.flush(reqItem({ status: "extracted" }));

    flushList(httpMock, "doc-1", [reqItem({ status: "extracted" })]);
    fixture.detectChanges();

    expect(fixture.componentInstance.requirements()[0].accepted).toBeFalsy();
    expect(fixture.componentInstance.requirements()[0].rejected).toBeFalsy();
    // accept/reject buttons reappear
    expect(
      fixture.nativeElement.querySelector('[title="Akceptuj wymaganie"]'),
    ).toBeTruthy();
  });

  it("opens inline edit mode, then saves via PUT", async () => {
    const fixture = await createComponent();
    flushList(httpMock);
    fixture.detectChanges();

    const editBtn = fixture.nativeElement.querySelector(
      '[title="Edytuj wymaganie"]',
    ) as HTMLButtonElement;
    editBtn.click();
    fixture.detectChanges();

    // edit form visible
    expect(
      fixture.nativeElement.querySelector('[title="Zapisz zmiany"]'),
    ).toBeTruthy();

    const component = fixture.componentInstance;
    component.editText.set("Zaktualizowana treść wymagania.");
    component.editPriority.set("medium");
    fixture.detectChanges();

    const saveBtn = fixture.nativeElement.querySelector(
      '[title="Zapisz zmiany"]',
    ) as HTMLButtonElement;
    saveBtn.click();

    const putReq = httpMock.expectOne(
      `${apiUrl}/documents/doc-1/requirements/REQ-1`,
    );
    expect(putReq.request.method).toBe("PUT");
    expect(putReq.request.body).toEqual({
      text: "Zaktualizowana treść wymagania.",
      priority: "medium",
    });
    putReq.flush(reqItem({ status: "edited" }));

    flushList(httpMock, "doc-1", [
      reqItem({
        text: "Zaktualizowana treść wymagania.",
        priority: "medium",
        status: "edited",
      }),
    ]);
    fixture.detectChanges();

    // edit form closed after save
    expect(component.editingReqId()).toBeNull();
    expect(fixture.nativeElement.textContent).toContain(
      "Zaktualizowana treść wymagania.",
    );
  });

  it("renders the LLM reasoning section when reasoning is present (Story 2.5)", async () => {
    const fixture = await createComponent();
    const llmReq = reqItem({
      req_id: "FR-LLM-1",
      text: "System musi logować wszystkie zdarzenia logowania.",
      extraction_method: "llm",
      reasoning: "Wymaganie audytowe bezpieczeństwa.",
    });
    flushList(httpMock, "doc-1", [llmReq]);
    fixture.detectChanges();

    const reasoning = fixture.nativeElement.querySelector(
      ".reasoning-text",
    ) as HTMLElement;
    expect(reasoning).toBeTruthy();
    expect(reasoning.textContent).toContain(
      "Wymaganie audytowe bezpieczeństwa.",
    );
    // the label is shown too
    expect(fixture.nativeElement.textContent).toContain("Uzasadnienie LLM");
  });

  it("does not render the reasoning section when reasoning is absent", async () => {
    const fixture = await createComponent();
    flushList(httpMock); // default reqItem has no reasoning
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector(".reasoning-text")).toBeFalsy();
  });
});
