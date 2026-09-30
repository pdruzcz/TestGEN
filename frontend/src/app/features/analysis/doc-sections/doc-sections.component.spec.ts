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
import { environment } from "../../../../environments/environment";
import { DocSectionsComponent } from "./doc-sections.component";
import { DocSection } from "./doc-sections.service";

const apiUrl = environment.apiUrl;

function routeStub(documentId: string, projectId = "p1"): ActivatedRoute {
  return {
    snapshot: {
      paramMap: {
        get: (key: string) =>
          key === "documentId"
            ? documentId
            : key === "projectId"
              ? projectId
              : null,
      },
    },
  } as unknown as ActivatedRoute;
}

function sectionTree(): DocSection[] {
  return [
    {
      sectionId: "s1",
      title: "Wprowadzenie",
      level: 1,
      content: "Treść wprowadzenia",
      pageNumber: 1,
      position: 0,
      sectionType: "unclassified",
      parentSectionId: null,
      children: [
        {
          sectionId: "s2",
          title: "Podsekcja",
          level: 2,
          content: "Treść podsekcji",
          pageNumber: 1,
          position: 1,
          sectionType: "unclassified",
          parentSectionId: "s1",
          children: [],
        },
      ],
    },
  ];
}

describe("DocSectionsComponent", () => {
  let httpMock: HttpTestingController;

  async function createComponent(documentId = "doc-1") {
    await TestBed.configureTestingModule({
      imports: [DocSectionsComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub(documentId) },
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(DocSectionsComponent);
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

  it("should create and request sections on init", async () => {
    const fixture = await createComponent();

    const req = httpMock.expectOne(`${apiUrl}/documents/doc-1/sections`);
    expect(req.request.method).toBe("GET");
    req.flush({
      document_id: "doc-1",
      filename: "spec.pdf",
      total: 1,
      sections: [],
    });

    expect(fixture.componentInstance).toBeTruthy();
    expect(fixture.componentInstance.isLoading()).toBe(false);
  });

  it("should render the section tree after load", async () => {
    const fixture = await createComponent();

    const req = httpMock.expectOne(`${apiUrl}/documents/doc-1/sections`);
    req.flush({
      document_id: "doc-1",
      filename: "spec.pdf",
      total: 1,
      sections: sectionTree(),
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain("Sekcje dokumentu: spec.pdf");
    expect(text).toContain("Wprowadzenie");
    expect(fixture.componentInstance.sections().length).toBe(1);
  });

  it("should show the empty state when there are no sections", async () => {
    const fixture = await createComponent();

    const req = httpMock.expectOne(`${apiUrl}/documents/doc-1/sections`);
    req.flush({
      document_id: "doc-1",
      filename: "empty.pdf",
      total: 0,
      sections: [],
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      "Brak sekcji do wyświetlenia.",
    );
  });

  it("should populate the content pane when a section is selected", async () => {
    const fixture = await createComponent();

    const req = httpMock.expectOne(`${apiUrl}/documents/doc-1/sections`);
    req.flush({
      document_id: "doc-1",
      filename: "spec.pdf",
      total: 1,
      sections: sectionTree(),
    });
    fixture.detectChanges();

    const root = fixture.componentInstance.sections()[0];
    fixture.componentInstance.selectSection(root);
    fixture.detectChanges();

    expect(fixture.componentInstance.selectedSection()?.sectionId).toBe("s1");
    expect(fixture.nativeElement.textContent).toContain("Treść wprowadzenia");
  });

  it("should map section_type to a Polish label", async () => {
    const fixture = await createComponent();
    const component = fixture.componentInstance;

    expect(component.typeLabel("functional")).toBe("Funkcjonalna");
    expect(component.typeLabel("non_functional")).toBe("Niefunkcjonalna");
    expect(component.typeLabel("instruction")).toBe("Instrukcja");
    expect(component.typeLabel("unclassified")).toBe("Niesklasyfikowana");

    // drain the init GET so afterEach.verify stays clean
    const req = httpMock.expectOne(`${apiUrl}/documents/doc-1/sections`);
    req.flush({
      document_id: "doc-1",
      filename: "spec.pdf",
      total: 0,
      sections: [],
    });
  });
});
