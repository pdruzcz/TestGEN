import { TestBed } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ProjectFilesService } from "./project-files.service";
import { environment } from "../../../../environments/environment";

describe("ProjectFilesService", () => {
  let service: ProjectFilesService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ProjectFilesService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should POST multipart form data to /projects/:id/upload", () => {
    const projectId = "11111111-1111-1111-1111-111111111111";
    const files = [
      new File(["print('x')"], "service.py", { type: "text/x-python" }),
    ];

    service.uploadFiles(projectId, files).subscribe();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/upload`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toBeInstanceOf(FormData);
    req.flush({
      project_id: projectId,
      accepted_files: [],
      rejected_files: [],
      total_accepted: 0,
      total_rejected: 0,
    });
  });

  it("should POST camelCase body to /projects/:id/connect-repo", () => {
    const projectId = "22222222-2222-2222-2222-222222222222";

    service
      .connectRepo(projectId, {
        repoUrl: "https://github.com/org/repo.git",
        branch: "main",
        authToken: "tk_123",
      })
      .subscribe();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/connect-repo`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      repoUrl: "https://github.com/org/repo.git",
      branch: "main",
      authToken: "tk_123",
    });
    req.flush({
      project_id: projectId,
      repo_url: "https://github.com/org/repo.git",
      branch: "main",
      files_indexed: 0,
      message: "ok",
    });
  });

  it("should GET the file list with pagination params", () => {
    const projectId = "33333333-3333-3333-3333-333333333333";

    service.listFiles(projectId, 2, 10).subscribe();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/files?page=2&page_size=10`,
    );
    expect(req.request.method).toBe("GET");
    req.flush({ files: [], total: 0 });
  });

  it("should default authToken to null when not provided", () => {
    const projectId = "44444444-4444-4444-4444-444444444444";

    service
      .connectRepo(projectId, {
        repoUrl: "https://gitlab.com/group/project.git",
        branch: "develop",
      })
      .subscribe();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/connect-repo`,
    );
    expect(req.request.body.authToken).toBeNull();
    req.flush({
      project_id: projectId,
      repo_url: "https://gitlab.com/group/project.git",
      branch: "develop",
      files_indexed: 0,
      message: "ok",
    });
  });

  it("should POST to /projects/:id/files/:fileId/analyze", () => {
    const projectId = "55555555-5555-5555-5555-555555555555";
    const fileId = "66666666-6666-6666-6666-666666666666";

    service.analyzeFile(projectId, fileId).subscribe();

    const req = httpTesting.expectOne(
      `${environment.apiUrl}/projects/${projectId}/files/${fileId}/analyze`,
    );
    expect(req.request.method).toBe("POST");
    req.flush({
      analysis: {
        raw_response: '{"structures": []}',
        model: "glm-5.1",
        usage: {},
      },
      file_id: fileId,
      project_id: projectId,
    });
  });
});
