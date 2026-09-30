import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../../environments/environment";

/**
 * HTTP wrapper for Epic 3, Story 3.15 (UML/GUI → user flow → Gherkin test →
 * coverage traceability matrix).
 *
 * Response payloads arrive after the global snakeCaseInterceptor has
 * transformed keys, so camelCase interfaces are declared client-side.
 */

export type CoverageStatus = "covered" | "partial" | "uncovered";
export type SourceType = "uml" | "gui";
export type ExportFormat = "csv" | "xlsx" | "json" | "pdf";

export interface TraceabilityEntry {
  id: string;
  sourceType: string;
  sourceElementId: string;
  sourceElementType: string;
  sourceElementName: string;
  sourceDiagramId: string | null;
  sourceScreenshotId: string | null;
  linkedFlowId: string | null;
  linkedGherkinId: string | null;
  testCaseId: string | null;
  codeReference: string | null;
  codeFramework: string | null;
  coverageStatus: CoverageStatus;
  createdAt: string | null;
}

export interface CoverageBreakdown {
  key: string;
  total: number;
  covered: number;
  partial: number;
  uncovered: number;
}

export interface TraceabilitySummary {
  umlTotal: number;
  guiTotal: number;
  umlCoveragePct: number;
  guiCoveragePct: number;
  codeCoveragePct: number;
  breakdownPerUmlType: CoverageBreakdown[];
  breakdownPerGuiCategory: CoverageBreakdown[];
}

export interface TraceabilityMatrix {
  elements: TraceabilityEntry[];
  summary: TraceabilitySummary;
  total: number;
  page: number;
  pageSize: number;
}

export interface TraceabilityBuildTask {
  taskId: string | null;
  status: string;
}

@Injectable({ providedIn: "root" })
export class TraceabilityService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Paginated, filterable traceability matrix plus its coverage summary. */
  getMatrix(
    projectId: string,
    options: {
      sourceType?: SourceType;
      coverageStatus?: CoverageStatus;
      page?: number;
      pageSize?: number;
    } = {},
  ): Observable<TraceabilityMatrix> {
    let params = new HttpParams()
      .set("page", String(options.page ?? 1))
      .set("page_size", String(options.pageSize ?? 20));
    if (options.sourceType) {
      params = params.set("source_type", options.sourceType);
    }
    if (options.coverageStatus) {
      params = params.set("coverage_status", options.coverageStatus);
    }
    return this.http.get<TraceabilityMatrix>(
      `${this.apiUrl}/projects/${projectId}/traceability`,
      { params },
    );
  }

  /** Trigger an asynchronous rebuild of the matrix. Returns 202 + task id. */
  build(projectId: string): Observable<TraceabilityBuildTask> {
    return this.http.post<TraceabilityBuildTask>(
      `${this.apiUrl}/projects/${projectId}/traceability/build`,
      {},
    );
  }

  /** Download the full matrix as a file blob in the requested format. */
  export(projectId: string, format: ExportFormat): Observable<Blob> {
    const params = new HttpParams().set("format", format);
    return this.http.get(
      `${this.apiUrl}/projects/${projectId}/traceability/export`,
      { params, responseType: "blob" },
    );
  }
}
