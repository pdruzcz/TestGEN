import { provideHttpClient, withInterceptors } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { provideAnimationsAsync } from "@angular/platform-browser/animations/async";
import { ActivatedRoute } from "@angular/router";

import { snakeCaseInterceptor } from "../../../../../core/interceptors/snake-case.interceptor";
import { environment } from "../../../../../../environments/environment";
import { UmlUploadComponent } from "./uml-upload.component";

const apiUrl = environment.apiUrl;

function routeStub(projectId = "p1"): ActivatedRoute {
  return {
    snapshot: {
      paramMap: {
        get: (key: string) => (key === "projectId" ? projectId : null),
      },
    },
  } as unknown as ActivatedRoute;
}

function file(name: string, type = ""): File {
  return new File(["payload"], name, { type });
}

describe("UmlUploadComponent", () => {
  let httpMock: HttpTestingController;

  async function createComponent(projectId = "p1") {
    await TestBed.configureTestingModule({
      imports: [UmlUploadComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
        provideAnimationsAsync(),
        { provide: ActivatedRoute, useValue: routeStub(projectId) },
      ],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(UmlUploadComponent);
    fixture.detectChanges(); // ngOnInit → GET list
    return fixture;
  }

  /** Flush the init list-diagrams GET triggered by ngOnInit. */
  function flushList(projectId = "p1") {
    const req = httpMock.expectOne(
      (r) =>
        r.method === "GET" && r.url === `${apiUrl}/projects/${projectId}/uml`,
    );
    req.flush({ diagrams: [], total: 0 });
  }

  afterEach(() => {
    httpMock
      .match(() => true)
      .forEach((r) => {
        try {
          // List-diagrams GETs must receive a valid body (component maps
          // `diagrams`); other pending requests can flush empty.
          if (r.request.method === "GET" && r.request.url.endsWith("/uml")) {
            r.flush({ diagrams: [], total: 0 });
          } else {
            r.flush({});
          }
        } catch {
          // already resolved
        }
      });
  });

  it("exposes visual extensions (SVG/PDF/PNG) in the allowed-extensions label", async () => {
    const fixture = await createComponent();
    flushList();

    const label = fixture.componentInstance.allowedExtensionsLabel;
    expect(label).toContain(".svg");
    expect(label).toContain(".pdf");
    expect(label).toContain(".png");
  });

  it("maps visual formats to distinct icons", async () => {
    const fixture = await createComponent();
    flushList();

    const c = fixture.componentInstance;
    expect(c.getDiagramIcon({ format: "xmi" } as never)).toBe("account_tree");
    expect(c.getDiagramIcon({ format: "plantuml" } as never)).toBe("schema");
    expect(c.getDiagramIcon({ format: "svg" } as never)).toBe("image");
    expect(c.getDiagramIcon({ format: "raster" } as never)).toBe("image");
    expect(c.getDiagramIcon({ format: "pdf" } as never)).toBe("picture_as_pdf");
  });

  it("accepts an SVG file and dispatches the upload request", async () => {
    const fixture = await createComponent();
    flushList();

    (
      fixture.componentInstance as unknown as {
        handleFiles: (f: File[]) => void;
      }
    ).handleFiles([file("diagram.svg", "image/svg+xml")]);

    const upload = httpMock.expectOne(
      (r) =>
        r.method === "POST" && r.url === `${apiUrl}/projects/p1/uml/upload`,
    );
    upload.flush({
      project_id: "p1",
      accepted: [],
      rejected: [],
      total_accepted: 0,
      total_rejected: 0,
    });

    expect(fixture.componentInstance.uploadError()).toBe("");
  });

  it("rejects a non-UML file client-side without calling the API", async () => {
    const fixture = await createComponent();
    flushList();

    (
      fixture.componentInstance as unknown as {
        handleFiles: (f: File[]) => void;
      }
    ).handleFiles([file("archive.zip")]);

    httpMock.expectNone(
      (r) =>
        r.method === "POST" && r.url === `${apiUrl}/projects/p1/uml/upload`,
    );
    expect(fixture.componentInstance.uploadError()).toContain(
      "Nieobsługiwany format",
    );
  });
});
