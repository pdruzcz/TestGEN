import { TestBed } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { firstValueFrom } from "rxjs";
import { CodegenService } from "./codegen.service";
import { environment } from "../../../../../environments/environment";

describe("CodegenService", () => {
  let service: CodegenService;
  let httpTesting: HttpTestingController;
  const apiUrl = environment.apiUrl;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        CodegenService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(CodegenService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  it("generateDatabase dispatches POST /codegen/database with database framework", async () => {
    const projectId = "proj-1";
    const testCaseIds = ["tc-1", "tc-2"];
    const promise = firstValueFrom(
      service.generateDatabase(projectId, testCaseIds),
    );

    const req = httpTesting.expectOne(
      `${apiUrl}/projects/${projectId}/codegen/database`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      test_case_ids: testCaseIds,
      framework: "database",
    });
    req.flush({ taskId: "task-db", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-db");
    expect(task.status).toBe("pending");
  });

  it("generateCypress still dispatches the cypress endpoint", async () => {
    const promise = firstValueFrom(
      service.generateCypress("p", ["a"], "https://x"),
    );
    const req = httpTesting.expectOne(`${apiUrl}/projects/p/codegen/cypress`);
    expect(req.request.body.framework).toBe("cypress");
    req.flush({ taskId: "task-cy", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-cy");
  });

  it("generatePhpUnit dispatches POST /codegen/phpunit (Story 1.55)", async () => {
    const projectId = "proj-php";
    const testCaseIds = ["tc-1", "tc-2"];
    const promise = firstValueFrom(
      service.generatePhpUnit(projectId, testCaseIds),
    );

    const req = httpTesting.expectOne(
      `${apiUrl}/projects/${projectId}/codegen/phpunit`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      test_case_ids: testCaseIds,
      framework: "phpunit",
    });
    req.flush({ taskId: "task-phpunit", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-phpunit");
    expect(task.status).toBe("pending");
  });

  it("generatePest dispatches POST /codegen/pest (Story 1.55)", async () => {
    const projectId = "proj-php";
    const testCaseIds = ["tc-1"];
    const promise = firstValueFrom(
      service.generatePest(projectId, testCaseIds),
    );

    const req = httpTesting.expectOne(
      `${apiUrl}/projects/${projectId}/codegen/pest`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      test_case_ids: testCaseIds,
      framework: "pest",
    });
    req.flush({ taskId: "task-pest", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-pest");
  });

  it("generateSelenium dispatches POST /codegen/selenium (Story 1.56)", async () => {
    const projectId = "proj-e2e";
    const testCaseIds = ["tc-1", "tc-2"];
    const promise = firstValueFrom(
      service.generateSelenium(projectId, testCaseIds),
    );

    const req = httpTesting.expectOne(
      `${apiUrl}/projects/${projectId}/codegen/selenium`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      test_case_ids: testCaseIds,
      framework: "selenium",
    });
    req.flush({ taskId: "task-sel", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-sel");
  });

  it("generatePlaywright dispatches POST /codegen/playwright (Story 1.56)", async () => {
    const projectId = "proj-e2e";
    const testCaseIds = ["tc-1"];
    const promise = firstValueFrom(
      service.generatePlaywright(projectId, testCaseIds),
    );

    const req = httpTesting.expectOne(
      `${apiUrl}/projects/${projectId}/codegen/playwright`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      test_case_ids: testCaseIds,
      framework: "playwright",
    });
    req.flush({ taskId: "task-pw", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-pw");
  });

  it("generateAppium dispatches POST /codegen/appium with platform (Story 1.56)", async () => {
    const projectId = "proj-e2e";
    const testCaseIds = ["tc-1"];
    const promise = firstValueFrom(
      service.generateAppium(projectId, testCaseIds, "ios"),
    );

    const req = httpTesting.expectOne(
      `${apiUrl}/projects/${projectId}/codegen/appium`,
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      test_case_ids: testCaseIds,
      framework: "appium",
      platform: "ios",
    });
    req.flush({ taskId: "task-ap", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-ap");
  });

  it("generateAppium omits platform when not provided (Story 1.56)", async () => {
    const promise = firstValueFrom(service.generateAppium("p", ["a"]));

    const req = httpTesting.expectOne(`${apiUrl}/projects/p/codegen/appium`);
    expect(req.request.body).toEqual({
      test_case_ids: ["a"],
      framework: "appium",
    });
    req.flush({ taskId: "task-ap2", status: "pending" });

    await promise;
  });

  it("generateUnittest dispatches POST /codegen/unittest (Story 1.57)", async () => {
    const promise = firstValueFrom(service.generateUnittest("p", ["a"]));

    const req = httpTesting.expectOne(`${apiUrl}/projects/p/codegen/unittest`);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({
      test_case_ids: ["a"],
      framework: "unittest",
    });
    req.flush({ taskId: "task-ut", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-ut");
  });

  it("generateTestNg dispatches POST /codegen/testng (Story 1.57)", async () => {
    const promise = firstValueFrom(service.generateTestNg("p", ["a"]));

    const req = httpTesting.expectOne(`${apiUrl}/projects/p/codegen/testng`);
    expect(req.request.body).toEqual({
      test_case_ids: ["a"],
      framework: "testng",
    });
    req.flush({ taskId: "task-tng", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-tng");
  });

  it("generateMsTest dispatches POST /codegen/mstest (Story 1.57)", async () => {
    const promise = firstValueFrom(service.generateMsTest("p", ["a"]));

    const req = httpTesting.expectOne(`${apiUrl}/projects/p/codegen/mstest`);
    expect(req.request.body).toEqual({
      test_case_ids: ["a"],
      framework: "mstest",
    });
    req.flush({ taskId: "task-mst", status: "pending" });

    const task = await promise;
    expect(task.taskId).toBe("task-mst");
  });

  it("getCode fetches a generated code record", async () => {
    const promise = firstValueFrom(service.getCode("p", "code-1"));
    const req = httpTesting.expectOne(`${apiUrl}/projects/p/codegen/code-1`);
    expect(req.request.method).toBe("GET");
    req.flush({
      id: "code-1",
      test_case_id: "tc-1",
      framework: "pytest",
      language: "python",
      code: "def test_x(): pass",
      file_path: "tests/db/test_users.py",
      created_at: null,
    });

    const code = await promise;
    expect(code.framework).toBe("pytest");
    expect(code.language).toBe("python");
  });
});
