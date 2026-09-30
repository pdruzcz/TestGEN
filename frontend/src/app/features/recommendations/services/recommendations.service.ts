import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../environments/environment";

export interface Recommendation {
  id: string;
  project_id: string;
  gap_finding_id: string | null;
  code_error_id: string | null;
  title: string;
  description: string;
  priority: string;
  confidence: number;
  source_type: string;
  source_ref: string | null;
  suggestion: string | null;
  context: Record<string, unknown> | null;
  created_at: string;
}

export interface RecommendationSummary {
  total: number;
  by_priority: Record<string, number>;
  avg_confidence: number;
  low_confidence_count: number;
}

export interface RecommendationsListResponse {
  recommendations: Recommendation[];
  total: number;
  page: number;
  size: number;
  summary: RecommendationSummary;
}

export interface RecommendationGenerateResponse {
  task_id: string;
  status: string;
}

@Injectable({ providedIn: "root" })
export class RecommendationsService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  generate(
    projectId: string,
    sources?: string[],
  ): Observable<RecommendationGenerateResponse> {
    return this.http.post<RecommendationGenerateResponse>(
      `${this.apiUrl}/projects/${projectId}/recommendations/generate`,
      { sources: sources ?? ["gap_finding", "code_error"] },
    );
  }

  getRecommendations(
    projectId: string,
    options?: {
      priority?: string;
      source_type?: string;
      min_confidence?: number;
      page?: number;
      size?: number;
    },
  ): Observable<RecommendationsListResponse> {
    const params = new URLSearchParams();
    if (options?.priority) params.set("priority", options.priority);
    if (options?.source_type) params.set("source_type", options.source_type);
    if (options?.min_confidence)
      params.set("min_confidence", String(options.min_confidence));
    if (options?.page) params.set("page", String(options.page));
    if (options?.size) params.set("size", String(options.size));
    const qs = params.toString();
    const url = `${this.apiUrl}/projects/${projectId}/recommendations`;
    return this.http.get<RecommendationsListResponse>(qs ? `${url}?${qs}` : url);
  }

  getSummary(projectId: string): Observable<RecommendationSummary> {
    return this.http.get<RecommendationSummary>(
      `${this.apiUrl}/projects/${projectId}/recommendations/summary`,
    );
  }
}
