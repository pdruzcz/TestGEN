import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { environment } from "../../../../environments/environment";
import { Project } from "../models/project.model";
import { ProjectService } from "./project.service";

const apiUrl = `${environment.apiUrl}/projects`;

const mockProject: Project = {
  id: "p1",
  tenantId: "t1",
  name: "Mój projekt",
  description: "Opis",
  languageHint: "python",
  status: "active",
  createdAt: "2026-04-16T10:00:00Z",
  updatedAt: "2026-04-16T10:00:00Z",
};

describe("ProjectService", () => {
  let service: ProjectService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        ProjectService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(ProjectService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  describe("initial signal state", () => {
    it("should start with empty projects", () => {
      expect(service.projectsSignal()).toEqual([]);
    });

    it("should start with total=0", () => {
      expect(service.totalSignal()).toBe(0);
    });

    it("should start with isLoading=false", () => {
      expect(service.isLoadingSignal()).toBe(false);
    });
  });

  describe("list()", () => {
    it("should GET /projects without params when query is empty", () => {
      service.list().subscribe();
      const req = httpTesting.expectOne((r) => r.url === apiUrl);
      expect(req.request.method).toBe("GET");
      expect(req.request.params.keys()).toEqual([]);
      req.flush({ projects: [], total: 0 });
    });

    it("should send snake_case query params for page/page_size/sort", () => {
      service
        .list({
          page: 2,
          pageSize: 50,
          status: "active",
          language: "python",
          sortBy: "name",
          sortOrder: "asc",
        })
        .subscribe();

      const req = httpTesting.expectOne((r) => r.url === apiUrl);
      expect(req.request.params.get("page")).toBe("2");
      expect(req.request.params.get("page_size")).toBe("50");
      expect(req.request.params.get("status")).toBe("active");
      expect(req.request.params.get("language")).toBe("python");
      expect(req.request.params.get("sort_by")).toBe("name");
      expect(req.request.params.get("sort_order")).toBe("asc");
      req.flush({ projects: [], total: 0 });
    });

    it("should prefer X-Total-Count header over body.total for total", () => {
      service.list({ page: 1, pageSize: 20 }).subscribe((result) => {
        expect(result.total).toBe(42);
        expect(result.projects).toEqual([mockProject]);
      });

      const req = httpTesting.expectOne((r) => r.url === apiUrl);
      req.flush(
        { projects: [mockProject], total: 99 },
        { headers: { "X-Total-Count": "42" } },
      );
    });

    it("should update signals with fetched projects and total", () => {
      service.list().subscribe();
      const req = httpTesting.expectOne((r) => r.url === apiUrl);
      req.flush(
        { projects: [mockProject], total: 7 },
        { headers: { "X-Total-Count": "7" } },
      );

      expect(service.projectsSignal()).toEqual([mockProject]);
      expect(service.totalSignal()).toBe(7);
      expect(service.isLoadingSignal()).toBe(false);
    });

    it("should clear isLoading on error", () => {
      service.list().subscribe({ error: () => undefined });
      const req = httpTesting.expectOne((r) => r.url === apiUrl);
      req.flush(null, { status: 500, statusText: "Server Error" });
      expect(service.isLoadingSignal()).toBe(false);
    });

    it("should skip falsy filters (empty string, null)", () => {
      service
        .list({ page: 1, pageSize: 20, status: null, language: "" })
        .subscribe();
      const req = httpTesting.expectOne((r) => r.url === apiUrl);
      expect(req.request.params.has("status")).toBe(false);
      expect(req.request.params.has("language")).toBe(false);
      req.flush({ projects: [], total: 0 });
    });
  });

  describe("get()", () => {
    it("should GET /projects/{id}", () => {
      service.get("p1").subscribe((p) => expect(p).toEqual(mockProject));
      const req = httpTesting.expectOne(`${apiUrl}/p1`);
      expect(req.request.method).toBe("GET");
      req.flush(mockProject);
    });
  });

  describe("create()", () => {
    it("should POST /projects with camelCase body", () => {
      service
        .create({
          name: "Nowy",
          description: "x",
          languageHint: "python",
        })
        .subscribe((p) => expect(p).toEqual(mockProject));

      const req = httpTesting.expectOne(apiUrl);
      expect(req.request.method).toBe("POST");
      expect(req.request.body).toEqual({
        name: "Nowy",
        description: "x",
        languageHint: "python",
      });
      req.flush(mockProject);
    });
  });

  describe("update()", () => {
    it("should PUT /projects/{id} with partial body", () => {
      service
        .update("p1", { name: "Zmieniony" })
        .subscribe((p) => expect(p).toEqual(mockProject));

      const req = httpTesting.expectOne(`${apiUrl}/p1`);
      expect(req.request.method).toBe("PUT");
      expect(req.request.body).toEqual({ name: "Zmieniony" });
      req.flush(mockProject);
    });
  });

  describe("delete()", () => {
    it("should DELETE /projects/{id}", () => {
      let completed = false;
      service.delete("p1").subscribe({ complete: () => (completed = true) });

      const req = httpTesting.expectOne(`${apiUrl}/p1`);
      expect(req.request.method).toBe("DELETE");
      req.flush(null, { status: 204, statusText: "No Content" });
      expect(completed).toBe(true);
    });
  });
});
