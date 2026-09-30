import { HttpClient, HttpParams, HttpResponse } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, map, tap } from "rxjs";
import { environment } from "../../../../environments/environment";
import {
  BulkActionResponse,
  TestCase,
  TestCaseBulkUpdatePayload,
  TestCaseCreatePayload,
  TestCaseExecution,
  TestCaseHistoryResponse,
  TestCaseListQuery,
  TestCaseListResponse,
  TestCaseUpdatePayload,
  StatusCounts,
} from "../models/test-case.model";

@Injectable({ providedIn: "root" })
export class TestCaseService {
  private readonly apiUrl = `${environment.apiUrl}/test-cases`;
  private readonly http = inject(HttpClient);

  readonly testCasesSignal = signal<TestCase[]>([]);
  readonly totalSignal = signal(0);
  readonly statusCountsSignal = signal<StatusCounts>({
    ready: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    draft: 0,
    disabled: 0,
  });
  readonly isLoadingSignal = signal(false);

  list(query: TestCaseListQuery = {}): Observable<TestCaseListResponse> {
    let params = new HttpParams();
    if (query.projectId) params = params.set("project_id", query.projectId);
    if (query.page != null) params = params.set("page", String(query.page));
    if (query.pageSize != null)
      params = params.set("page_size", String(query.pageSize));
    if (query.analysisResultId)
      params = params.set("analysis_result_id", query.analysisResultId);
    if (query.sourceFileId)
      params = params.set("source_file_id", query.sourceFileId);
    if (query.type) params = params.set("type", query.type);
    if (query.status) params = params.set("status", query.status);
    if (query.framework) params = params.set("framework", query.framework);
    if (query.priority) params = params.set("priority", query.priority);
    if (query.sortBy) params = params.set("sort_by", query.sortBy);
    if (query.sortOrder) params = params.set("sort_order", query.sortOrder);

    this.isLoadingSignal.set(true);
    return this.http
      .get<TestCaseListResponse>(this.apiUrl, {
        params,
        observe: "response",
      })
      .pipe(
        map((resp: HttpResponse<TestCaseListResponse>) => {
          const body = resp.body ?? {
            testCases: [],
            total: 0,
            statusCounts: {
              ready: 0,
              passed: 0,
              failed: 0,
              skipped: 0,
              draft: 0,
              disabled: 0,
            },
          };
          const headerTotal = Number(
            resp.headers.get("X-Total-Count") ?? body.total,
          );
          return {
            testCases: body.testCases ?? [],
            total: Number.isFinite(headerTotal) ? headerTotal : body.total,
            statusCounts: body.statusCounts ?? {
              ready: 0,
              passed: 0,
              failed: 0,
              skipped: 0,
              draft: 0,
              disabled: 0,
            },
          } satisfies TestCaseListResponse;
        }),
        tap({
          next: (result) => {
            this.testCasesSignal.set(result.testCases);
            this.totalSignal.set(result.total);
            this.statusCountsSignal.set(result.statusCounts);
            this.isLoadingSignal.set(false);
          },
          error: () => this.isLoadingSignal.set(false),
        }),
      );
  }

  get(testCaseId: string): Observable<TestCase> {
    return this.http.get<TestCase>(`${this.apiUrl}/${testCaseId}`);
  }

  create(payload: TestCaseCreatePayload): Observable<TestCase> {
    return this.http.post<TestCase>(this.apiUrl, payload);
  }

  update(
    testCaseId: string,
    payload: TestCaseUpdatePayload,
  ): Observable<TestCase> {
    return this.http.put<TestCase>(`${this.apiUrl}/${testCaseId}`, payload);
  }

  delete(testCaseId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${testCaseId}`);
  }

  updateStatus(testCaseId: string, status: string): Observable<TestCase> {
    return this.http.patch<TestCase>(`${this.apiUrl}/${testCaseId}/status`, {
      status,
    });
  }

  execute(testCaseId: string): Observable<{ task_id: string }> {
    return this.http.post<{ task_id: string }>(
      `${this.apiUrl}/${testCaseId}/execute`,
      {},
    );
  }

  listExecutions(testCaseId: string): Observable<TestCaseExecution[]> {
    return this.http.get<TestCaseExecution[]>(
      `${this.apiUrl}/${testCaseId}/executions`,
    );
  }

  review(testCaseId: string): Observable<TestCase> {
    return this.http.post<TestCase>(`${this.apiUrl}/${testCaseId}/review`, {});
  }

  /** Story 6.5, AC5 — zbiorcza zmiana statusu/priorytetu. */
  bulkUpdate(
    payload: TestCaseBulkUpdatePayload,
  ): Observable<BulkActionResponse> {
    return this.http.post<BulkActionResponse>(
      `${this.apiUrl}/bulk-update`,
      payload,
    );
  }

  /** Story 6.5, AC5 — zbiorcze usuwanie. */
  bulkDelete(ids: string[]): Observable<BulkActionResponse> {
    return this.http.post<BulkActionResponse>(`${this.apiUrl}/bulk-delete`, {
      ids,
    });
  }

  /** Story 6.5, AC7 — historia zmian test case'a (audit log). */
  getHistory(testCaseId: string): Observable<TestCaseHistoryResponse> {
    return this.http.get<TestCaseHistoryResponse>(
      `${this.apiUrl}/${testCaseId}/history`,
    );
  }
}
