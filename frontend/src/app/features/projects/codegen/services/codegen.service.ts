import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../../environments/environment";

/**
 * HTTP wrapper for Epic 3, Story 3.12 (Cypress test code generation).
 *
 * Response payloads arrive after the global snakeCaseInterceptor has
 * transformed keys, so camelCase interfaces are declared client-side.
 */

export type CodeGenFramework =
  | "cypress"
  | "sikulix"
  | "database"
  | "phpunit"
  | "pest"
  | "selenium"
  | "playwright"
  | "appium"
  | "unittest"
  | "testng"
  | "mstest";

export interface CodeGenTask {
  taskId: string | null;
  status: string;
}

export interface GeneratedTestCode {
  id: string;
  testCaseId: string;
  framework: string;
  language: string;
  code: string;
  filePath: string | null;
  createdAt: string | null;
}

@Injectable({ providedIn: "root" })
export class CodegenService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Launch asynchronous Cypress code generation. Returns 202 + task id. */
  generateCypress(
    projectId: string,
    testCaseIds: string[],
    baseUrl?: string,
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/cypress`,
      {
        test_case_ids: testCaseIds,
        framework: "cypress",
        base_url: baseUrl ?? null,
      },
    );
  }

  /** Launch asynchronous SikuliX (image-based) code generation. Returns 202 + task id. */
  generateSikulix(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/sikulix`,
      {
        test_case_ids: testCaseIds,
        framework: "sikulix",
      },
    );
  }

  /**
   * Launch asynchronous database-layer (pytest) code generation.
   * Story 1.53 (FR70). Mirrors Cypress/SikuliX dispatch — generates isolated
   * pytest code (db_session + rollback) from `test_type = database` cases.
   * Returns 202 + task id.
   */
  generateDatabase(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/database`,
      {
        test_case_ids: testCaseIds,
        framework: "database",
      },
    );
  }

  /**
   * Launch asynchronous PHPUnit (PHP) code generation.
   * Story 1.55 (FR24/FR12) — generates a PHPUnit test class
   * (`extends TestCase`, `assertSame`, `expectException`).
   * Returns 202 + task id.
   */
  generatePhpUnit(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/phpunit`,
      {
        test_case_ids: testCaseIds,
        framework: "phpunit",
      },
    );
  }

  /**
   * Launch asynchronous Pest (PHP) code generation.
   * Story 1.55 (FR24/FR12) — generates Pest DSL tests
   * (`it()`, `expect()->toBe()`, `toThrow`).
   * Returns 202 + task id.
   */
  generatePest(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/pest`,
      {
        test_case_ids: testCaseIds,
        framework: "pest",
      },
    );
  }

  /**
   * Launch asynchronous Selenium (Python) code generation.
   * Story 1.56 — generates Selenium WebDriver tests (`.py`) from the
   * selected test cases. Returns 202 + task id.
   */
  generateSelenium(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/selenium`,
      {
        test_case_ids: testCaseIds,
        framework: "selenium",
      },
    );
  }

  /**
   * Launch asynchronous Playwright (TypeScript) code generation.
   * Story 1.56 — generates Playwright specs (`.spec.ts`) from the
   * selected test cases. Returns 202 + task id.
   */
  generatePlaywright(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/playwright`,
      {
        test_case_ids: testCaseIds,
        framework: "playwright",
      },
    );
  }

  /**
   * Launch asynchronous Appium (mobile, Python) code generation.
   * Story 1.56 — generates Appium tests (`.py`, AppiumBy + Page Object
   * Model) from the selected test cases. `platform` ("android"/"ios")
   * selects desired capabilities: UiAutomator2 / XCUITest.
   * Returns 202 + task id.
   */
  generateAppium(
    projectId: string,
    testCaseIds: string[],
    platform?: "android" | "ios",
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/appium`,
      {
        test_case_ids: testCaseIds,
        framework: "appium",
        ...(platform ? { platform } : {}),
      },
    );
  }

  /**
   * Launch asynchronous unittest (Python) code generation.
   * Story 1.57 — generates a `unittest.TestCase` class (assertEqual…,
   * runnable via `python -m unittest`) from the selected test cases.
   * Returns 202 + task id.
   */
  generateUnittest(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/unittest`,
      {
        test_case_ids: testCaseIds,
        framework: "unittest",
      },
    );
  }

  /**
   * Launch asynchronous TestNG (Java 11+) code generation.
   * Story 1.57 — generates a class with @Test/@BeforeMethod annotations
   * and Assert.assertEquals assertions. Returns 202 + task id.
   */
  generateTestNg(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/testng`,
      {
        test_case_ids: testCaseIds,
        framework: "testng",
      },
    );
  }

  /**
   * Launch asynchronous MSTest (.NET 8) code generation.
   * Story 1.57 — generates a [TestClass] with [TestMethod] methods and
   * Assert.AreEqual assertions. Returns 202 + task id.
   */
  generateMsTest(
    projectId: string,
    testCaseIds: string[],
  ): Observable<CodeGenTask> {
    return this.http.post<CodeGenTask>(
      `${this.apiUrl}/projects/${projectId}/codegen/mstest`,
      {
        test_case_ids: testCaseIds,
        framework: "mstest",
      },
    );
  }

  /** Fetch a generated test code record with its metadata. */
  getCode(projectId: string, codeId: string): Observable<GeneratedTestCode> {
    return this.http.get<GeneratedTestCode>(
      `${this.apiUrl}/projects/${projectId}/codegen/${codeId}`,
    );
  }
}
