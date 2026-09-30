import { HttpClient } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable } from "rxjs";
import { environment } from "../../../../environments/environment";
import { AnalysisResult } from "../../test-cases/models/test-case.model";

// camelCase — snakeCaseInterceptor converts all API responses from snake_case
export interface TaskStatusResponse {
  taskId: string;
  status: string;
  progress: number;
  currentStep: string;
  resultUrl: string | null;
  error: string | null;
}

/**
 * Konfiguracja analizy przekazywana do POST /analyze (Story 6.3).
 *
 * Story 6.3-zakończenie: `engine_mode` (native|llm|hybrid) oraz opcje LLM
 * (model/temperatura/maxTokens) to konfiguracja systemu (config-only,
 * decyzja `engine_mode_not_user_controllable`) — NIE wybór użytkownika.
 * FE nie wysyła `engine_mode`; backend używa `get_settings().engine_mode`.
 */
export interface AnalysisConfig {
  modules: string[];
  testFramework: string | null;
  /** Story 1.53 (FR70) — zakresy generowanych testów (np. "database"). */
  testScopes?: string[];
}

export const AVAILABLE_MODULES: ReadonlyArray<{
  value: string;
  label: string;
}> = [
  { value: "code_analysis", label: "Analiza kodu" },
  { value: "test_generation", label: "Generowanie testów" },
  { value: "uml_analysis", label: "Analiza UML" },
  { value: "gui_analysis", label: "Analiza GUI" },
];

export const AVAILABLE_FRAMEWORKS: ReadonlyArray<{
  value: string;
  label: string;
}> = [
  { value: "pytest", label: "Pytest" },
  { value: "junit", label: "JUnit" },
  { value: "nunit", label: "NUnit" },
  { value: "cypress", label: "Cypress" },
  { value: "mocha", label: "Mocha/Jest" },
  // Story 1.56 (AC3) — generatory E2E dostępne też jako framework analizy
  { value: "selenium", label: "Selenium" },
  { value: "playwright", label: "Playwright" },
  { value: "appium", label: "Appium" },
  // Story 1.57 (AC3) — natywne frameworki wykrywane w projektach
  { value: "unittest", label: "unittest" },
  { value: "testng", label: "TestNG" },
  { value: "mstest", label: "MSTest" },
];

export const DEFAULT_ANALYSIS_CONFIG: AnalysisConfig = {
  modules: ["code_analysis"],
  testFramework: null,
  testScopes: [],
};

@Injectable({ providedIn: "root" })
export class AnalysisService {
  private readonly apiUrl = `${environment.apiUrl}`;
  private readonly http = inject(HttpClient);

  readonly isLoadingSignal = signal(false);

  startProjectAnalysis(
    projectId: string,
    config: AnalysisConfig = DEFAULT_ANALYSIS_CONFIG,
  ): Observable<{ taskId: string }> {
    this.isLoadingSignal.set(true);
    // Story 6.3-zakończenie: bez `engine_mode` — backend dobiera silnik
    // z konfiguracji systemu (engine_mode_not_user_controllable).
    const body: Record<string, unknown> = {
      modules: config.modules,
    };
    // Story 1.53 (FR70) — zakresy generowanych testów (np. "database")
    if (config.testScopes?.length) body["test_scopes"] = config.testScopes;
    if (config.testFramework) body["test_framework"] = config.testFramework;

    return this.http.post<{ taskId: string }>(
      `${this.apiUrl}/projects/${projectId}/analyze`,
      body,
    );
  }

  getTaskStatus(taskId: string): Observable<TaskStatusResponse> {
    return this.http.get<TaskStatusResponse>(`${this.apiUrl}/tasks/${taskId}`);
  }

  cancelTask(taskId: string): Observable<{ taskId: string; status: string }> {
    return this.http.post<{ taskId: string; status: string }>(
      `${this.apiUrl}/tasks/${taskId}/cancel`,
      {},
    );
  }

  analyzeFile(projectId: string, fileId: string): Observable<AnalysisResult> {
    return this.http.post<AnalysisResult>(
      `${this.apiUrl}/projects/${projectId}/files/${fileId}/analyze`,
      {},
    );
  }
}
