import { HttpClient, HttpParams, HttpResponse } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, map, tap } from "rxjs";
import { environment } from "../../../../environments/environment";
import {
  Project,
  ProjectCreatePayload,
  ProjectListQuery,
  ProjectListResponse,
  ProjectUpdatePayload,
} from "../models/project.model";

/**
 * HTTP + signal state for project CRUD.
 *
 * Mirrors the pattern used in AuthService:
 *  - state exposed as signals (projectsSignal, totalSignal, isLoadingSignal)
 *  - explicit mutation via list/create/update/delete methods
 *  - takeUntilDestroyed is applied by the consumer (component) so a service
 *    survives across route changes
 *
 * NOTE: query params must be snake_case — the snakeCaseInterceptor only
 * transforms request/response BODIES, not query strings.
 */
@Injectable({ providedIn: "root" })
export class ProjectService {
  private readonly apiUrl = `${environment.apiUrl}/projects`;
  private readonly http = inject(HttpClient);

  readonly projectsSignal = signal<Project[]>([]);
  readonly totalSignal = signal(0);
  readonly isLoadingSignal = signal(false);

  list(query: ProjectListQuery = {}): Observable<ProjectListResponse> {
    let params = new HttpParams();
    if (query.page != null) {
      params = params.set("page", String(query.page));
    }
    if (query.pageSize != null) {
      params = params.set("page_size", String(query.pageSize));
    }
    if (query.status) {
      params = params.set("status", query.status);
    }
    if (query.language) {
      params = params.set("language", query.language);
    }
    if (query.sortBy) {
      params = params.set("sort_by", query.sortBy);
    }
    if (query.sortOrder) {
      params = params.set("sort_order", query.sortOrder);
    }

    this.isLoadingSignal.set(true);
    return this.http
      .get<ProjectListResponse>(this.apiUrl, {
        params,
        observe: "response",
      })
      .pipe(
        map((resp: HttpResponse<ProjectListResponse>) => {
          const body = resp.body ?? { projects: [], total: 0 };
          const headerTotal = Number(resp.headers.get("X-Total-Count") ?? body.total);
          return {
            projects: body.projects ?? [],
            total: Number.isFinite(headerTotal) ? headerTotal : body.total,
          } satisfies ProjectListResponse;
        }),
        tap({
          next: (result) => {
            this.projectsSignal.set(result.projects);
            this.totalSignal.set(result.total);
            this.isLoadingSignal.set(false);
          },
          error: () => this.isLoadingSignal.set(false),
        }),
      );
  }

  get(projectId: string): Observable<Project> {
    return this.http.get<Project>(`${this.apiUrl}/${projectId}`);
  }

  create(payload: ProjectCreatePayload): Observable<Project> {
    return this.http.post<Project>(this.apiUrl, payload);
  }

  update(projectId: string, payload: ProjectUpdatePayload): Observable<Project> {
    return this.http.put<Project>(`${this.apiUrl}/${projectId}`, payload);
  }

  delete(projectId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${projectId}`);
  }
}
