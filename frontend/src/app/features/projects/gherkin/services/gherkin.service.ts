import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../../environments/environment";

/**
 * HTTP wrapper for Epic 3, Story 3.11 (Gherkin/BDD generation from user flows).
 *
 * Response payloads arrive after the global snakeCaseInterceptor has
 * transformed keys, so camelCase interfaces are declared client-side.
 */

export type GherkinStatus = "generated" | "validated" | "approved";

export type GherkinEngineMode = "native" | "llm" | "hybrid";

export interface GherkinStep {
  keyword: string;
  text: string;
}

export interface GherkinScenario {
  name: string;
  tags: string[];
  steps: GherkinStep[];
  examplesHeaders: string[];
  examplesRows: string[][];
}

export interface GherkinFeature {
  id: string;
  featureName: string;
  featureDescription: string | null;
  sourceFlowId: string | null;
  scenarios: GherkinScenario[];
  rawFeature: string;
  engineMode: string;
  validationWarnings: string[];
  status: GherkinStatus;
  createdAt: string | null;
}

export interface GherkinFeatureListItem {
  id: string;
  featureName: string;
  sourceFlowId: string | null;
  engineMode: string;
  status: GherkinStatus;
  createdAt: string | null;
}

export interface GherkinFeatureListResponse {
  features: GherkinFeatureListItem[];
  total: number;
}

export interface GherkinGenerateTask {
  taskId: string | null;
  status: string;
}

@Injectable({ providedIn: "root" })
export class GherkinService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Launch asynchronous Gherkin generation from user flows. Returns 202 + task id. */
  generate(
    projectId: string,
    flowIds: string[],
    featureName?: string,
  ): Observable<GherkinGenerateTask> {
    return this.http.post<GherkinGenerateTask>(
      `${this.apiUrl}/projects/${projectId}/gherkin/generate`,
      {
        flow_ids: flowIds,
        feature_name: featureName ?? null,
      },
    );
  }

  /** Paginated list of generated Gherkin features for a project. */
  listFeatures(
    projectId: string,
    page = 1,
    pageSize = 20,
  ): Observable<GherkinFeatureListResponse> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));

    return this.http.get<GherkinFeatureListResponse>(
      `${this.apiUrl}/projects/${projectId}/gherkin`,
      { params },
    );
  }

  /** Structured details of a single Gherkin feature. */
  getFeature(projectId: string, featureId: string): Observable<GherkinFeature> {
    return this.http.get<GherkinFeature>(
      `${this.apiUrl}/projects/${projectId}/gherkin/${featureId}`,
    );
  }

  /** Raw ``.feature`` text of a single Gherkin feature (format=raw). */
  getRawFeature(projectId: string, featureId: string): Observable<string> {
    const params = new HttpParams().set("format", "raw");
    return this.http.get(
      `${this.apiUrl}/projects/${projectId}/gherkin/${featureId}`,
      { params, responseType: "text" },
    );
  }
}
