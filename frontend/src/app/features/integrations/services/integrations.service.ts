import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../environments/environment";

export interface IntegrationConfig {
  id: string;
  projectId: string;
  provider: string;
  baseUrl: string;
  settings: Record<string, unknown> | null;
  isActive: boolean;
  createdAt: string;
}

export interface ConfigRequest {
  provider: "jira" | "azure_devops";
  baseUrl: string;
  email: string;
  apiToken: string;
  projectKey: string;
  issueType: string;
  organization: string;
  project: string;
}

export interface TestResponse {
  connected: boolean;
  message: string;
}

export interface SyncRequest {
  syncType: "gap_findings" | "recommendations";
}

export interface SyncResult {
  total: number;
  synced: number;
  errors: Array<Record<string, string>>;
}

export interface SyncLog {
  id: string;
  integrationConfigId: string;
  syncType: string;
  status: string;
  itemsTotal: number;
  itemsSynced: number;
  errors: Record<string, unknown> | null;
  createdAt: string;
  completedAt: string | null;
}

@Injectable({ providedIn: "root" })
export class IntegrationsService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  configure(
    projectId: string,
    req: ConfigRequest,
  ): Observable<IntegrationConfig> {
    return this.http.post<IntegrationConfig>(
      `${this.apiUrl}/projects/${projectId}/integrations/configure`,
      req,
    );
  }

  getConfig(
    projectId: string,
    provider: string = "jira",
  ): Observable<IntegrationConfig | null> {
    const params = new HttpParams().set("provider", provider);
    return this.http.get<IntegrationConfig | null>(
      `${this.apiUrl}/projects/${projectId}/integrations/config`,
      { params },
    );
  }

  testConnection(
    projectId: string,
    provider: string = "jira",
  ): Observable<TestResponse> {
    const params = new HttpParams().set("provider", provider);
    return this.http.post<TestResponse>(
      `${this.apiUrl}/projects/${projectId}/integrations/test`,
      {},
      { params },
    );
  }

  sync(
    projectId: string,
    req: SyncRequest,
    provider: string = "jira",
  ): Observable<SyncResult> {
    const params = new HttpParams().set("provider", provider);
    return this.http.post<SyncResult>(
      `${this.apiUrl}/projects/${projectId}/integrations/sync`,
      req,
      { params },
    );
  }

  getLogs(
    projectId: string,
    provider: string = "jira",
  ): Observable<SyncLog[]> {
    const params = new HttpParams().set("provider", provider);
    return this.http.get<SyncLog[]>(
      `${this.apiUrl}/projects/${projectId}/integrations/logs`,
      { params },
    );
  }
}
