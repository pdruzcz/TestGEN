import { provideHttpClient, withInterceptors } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";

import { snakeCaseInterceptor } from "../../../core/interceptors/snake-case.interceptor";
import { environment } from "../../../../environments/environment";
import { DocSectionsService } from "./doc-sections.service";

const apiUrl = environment.apiUrl;

describe("DocSectionsService", () => {
  let service: DocSectionsService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        DocSectionsService,
        // Include the global interceptor so the test exercises the real
        // snake_case → camelCase contract the component consumes.
        provideHttpClient(withInterceptors([snakeCaseInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(DocSectionsService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  describe("getSections()", () => {
    it("should GET /documents/{id}/sections", () => {
      const documentId = "doc-123";
      service.getSections(documentId).subscribe();

      const req = httpTesting.expectOne(
        `${apiUrl}/documents/${documentId}/sections`,
      );
      expect(req.request.method).toBe("GET");
      req.flush({ documentId, filename: "spec.pdf", total: 0, sections: [] });
    });

    it("should return the reconstructed tree (camelCase)", () => {
      const payload = {
        document_id: "doc-1",
        filename: "spec.pdf",
        total: 1,
        sections: [
          {
            section_id: "s1",
            title: "Wprowadzenie",
            level: 1,
            content: "treść",
            page_number: 1,
            position: 0,
            section_type: "unclassified",
            parent_section_id: null,
            children: [],
          },
        ],
      };

      service.getSections("doc-1").subscribe((response) => {
        // snake_case → camelCase happens via the interceptor in production;
        // here we assert the typed contract the component relies on.
        expect(response.documentId).toBe("doc-1");
        expect(response.total).toBe(1);
        expect(response.sections[0].sectionId).toBe("s1");
        expect(response.sections[0].sectionType).toBe("unclassified");
      });

      const req = httpTesting.expectOne(`${apiUrl}/documents/doc-1/sections`);
      req.flush(payload);
    });
  });

  describe("getSectionDetail()", () => {
    it("should GET /documents/{id}/sections/{sectionId}", () => {
      service.getSectionDetail("doc-1", "s1").subscribe();

      const req = httpTesting.expectOne(
        `${apiUrl}/documents/doc-1/sections/s1`,
      );
      expect(req.request.method).toBe("GET");
      req.flush({
        documentId: "doc-1",
        section: { sectionId: "s1", children: [] },
      });
    });
  });
});
