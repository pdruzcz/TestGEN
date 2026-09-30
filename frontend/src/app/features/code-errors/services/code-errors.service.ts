import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../environments/environment";

/**
 * UWAGA: pola camelCase — snakeCaseInterceptor (core/interceptors) zamienia
 * snake_case z API na camelCase w każdej odpowiedzi.
 */
export interface CodeError {
  id: string;
  projectId: string;
  sourceFileId: string | null;
  category: string;
  message: string;
  filePath: string | null;
  lineStart: number | null;
  lineEnd: number | null;
  severity: string;
  ruleId: string | null;
  suggestion: string | null;
  context: Record<string, unknown> | null;
  status?: string;
  fingerprint?: string | null;
  createdAt: string;
}

export interface CodeErrorSummary {
  totalErrors: number;
  byCategory: Record<string, number>;
  bySeverity: Record<string, number>;
}

export interface CodeErrorsListResponse {
  errors: CodeError[];
  total: number;
  page: number;
  size: number;
  summary: CodeErrorSummary;
}

export interface CodeErrorScanResponse {
  taskId: string;
  status: string;
}

@Injectable({ providedIn: "root" })
export class CodeErrorsService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  scan(
    projectId: string,
    categories?: string[],
  ): Observable<CodeErrorScanResponse> {
    return this.http.post<CodeErrorScanResponse>(
      `${this.apiUrl}/projects/${projectId}/code-errors/scan`,
      {
        categories: categories ?? [
          "syntax",
          "logic",
          "semantic",
          "conformance",
          "dead_code",
        ],
      },
    );
  }

  getErrors(
    projectId: string,
    options?: {
      category?: string;
      severity?: string;
      page?: number;
      size?: number;
    },
  ): Observable<CodeErrorsListResponse> {
    const params = new URLSearchParams();
    if (options?.category) params.set("category", options.category);
    if (options?.severity) params.set("severity", options.severity);
    if (options?.page) params.set("page", String(options.page));
    if (options?.size) params.set("size", String(options.size));
    const qs = params.toString();
    const url = `${this.apiUrl}/projects/${projectId}/code-errors`;
    return this.http.get<CodeErrorsListResponse>(qs ? `${url}?${qs}` : url);
  }

  getSummary(projectId: string): Observable<CodeErrorSummary> {
    return this.http.get<CodeErrorSummary>(
      `${this.apiUrl}/projects/${projectId}/code-errors/summary`,
    );
  }

  /** Story 5.10 (AC4) — odrzucenie znaleziska jako fałszywy pozytyw. */
  updateStatus(
    projectId: string,
    errorId: string,
    status: "open" | "false_positive",
  ): Observable<CodeError> {
    return this.http.patch<CodeError>(
      `${this.apiUrl}/projects/${projectId}/code-errors/${errorId}/status`,
      { status },
    );
  }
}
