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
import { DocumentViewComponent } from "./document-view.component";

const apiUrl = "/api/v1";

function routeStub(
  opts: { projectId?: string; documentId?: string; highlight?: string } = {},
): ActivatedRoute {
  const { projectId = "p1", documentId = "doc-1", highlight = "" } = opts;
  return {
    snapshot: {
      paramMap: {
        get: (key: string) =>
          key === "projectId"
            ? projectId
            : key === "documentId"
              ? documentId
              : null,
      },
      queryParamMap: {
        get: (key: string) => (key === "highlight" ? highlight : null),
      },
      queryParams: { highlight },
    },
  } as unknown as ActivatedRoute;
}

function sourceFileBody(): Record<string, unknown> {
  return {
    id: "doc-1",
    project_id: "p1",
    filename: "spec.pdf",
    file_size: 1024,
    file_category: "documentation",
    doc_format: "pdf",
    page_count: 3,
    created_at: "2026-01-01T00:00:00Z",
    is_cleaned_up: false,
    processing_status: "ready",
    error_message: null,
  };
}

function sectionsBody(): Record<string, unknown> {
  return {
    document_id: "doc-1",
    filename: "spec.pdf",
    total: 1,
    sections: [
      {
        section_id: "sec-1",
        title: "Wymagania funkcjonalne",
        level: 1,
        content: "System musi umożliwiać logowanie.",
        position: 0,
        section_type: "functional",
        page_number: 1,
        parent_section_id: null,
        children: [
          {
            section_id: "sec-1-1",
            title: "Logowanie",
            level: 2,
            content: "Logowanie przez adres e-mail.",
            position: 1,
            section_type: "functional",
            page_number: 1,
            parent_section_id: "sec-1",
            children: [],
          },
        ],
      },
    ],
  };
}

describe("DocumentViewComponent", () => {
  let httpMock: HttpTestingController;

  async function createComponent(
    opts: { projectId?: string; documentId?: string; highlight?: string } = {},
  ) {
    await TestBed.configureTestingModule({
      imports: [DocumentViewComponent],
      providers: [
        provideRouter([]),
        // Interceptor jak w runtime: odpowiedzi snake_case → camelCase.
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub(opts) },
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(DocumentViewComponent);
    fixture.detectChanges(); // triggers ngOnInit → forkJoin(GET meta, GET sections)
    return fixture;
  }

  function flushMeta() {
    const req = httpMock.expectOne(`${apiUrl}/projects/p1/documents/doc-1`);
    expect(req.request.method).toBe("GET");
    req.flush(sourceFileBody());
  }

  function flushSections(body = sectionsBody(), status = 200) {
    const req = httpMock.expectOne(`${apiUrl}/documents/doc-1/sections`);
    expect(req.request.method).toBe("GET");
    req.flush(body, { status, statusText: status === 200 ? "OK" : "Accepted" });
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

  it("renders parsed sections instead of the false 'not parsed' state — UI bug fix", async () => {
    const fixture = await createComponent();
    flushMeta();
    flushSections();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    // Drzewo spłaszczone: rodzic i dziecko renderują się po kolei.
    expect(text).toContain("Wymagania funkcjonalne");
    expect(text).toContain("Logowanie");
    expect(text).toContain("System musi umożliwiać logowanie.");
    expect(text).not.toContain("Dokument nie został jeszcze zaparsowany.");
  });

  it("shows the 'not parsed' state only when sections are genuinely unavailable (202)", async () => {
    const fixture = await createComponent();
    flushMeta();
    // Backend odpowiada 202 {detail: …} dopóki preprocessing trwa.
    flushSections({ detail: "Analiza w toku" }, 202);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      "Dokument nie został jeszcze zaparsowany.",
    );
  });

  it("hides the raw text tab when the backend provides no raw text", async () => {
    const fixture = await createComponent();
    flushMeta();
    flushSections();
    fixture.detectChanges();

    const tabLabels = Array.from<HTMLElement>(
      fixture.nativeElement.querySelectorAll(
        ".mat-mdc-tab .mdc-tab__text-label",
      ),
    ).map((el) => el.textContent?.trim());
    expect(tabLabels).not.toContain("Surowy tekst");
    expect(tabLabels).toContain("Sekcje");
  });

  it("scrolls to and highlights the ?highlight section after load", async () => {
    const fixture = await createComponent({ highlight: "sec-1-1" });
    flushMeta();
    flushSections();
    fixture.detectChanges();
    // applyHighlight czeka jedną turę na wyrenderowany DOM.
    await new Promise((resolve) => setTimeout(resolve, 0));

    const component = fixture.componentInstance;
    expect(component.activeSectionId()).toBe("sec-1-1");

    const highlighted = fixture.nativeElement.querySelector(
      ".document-section.highlighted",
    );
    expect(highlighted).toBeTruthy();
    expect(highlighted.textContent).toContain("Logowanie");
  });
});
