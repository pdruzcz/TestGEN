import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

/**
 * Klient integracji z hostingiem kodu (Story 8.1 — GitHub, 8.2 — GitLab).
 *
 * Interceptor `snakeCaseInterceptor` tłumaczy klucze w obie strony, więc
 * kontrakt po stronie Angulara jest w camelCase mimo snake_case w API.
 *
 * GitLab ma własne sygnały i metody, bo różni się trzema rzeczami: adresem
 * instancji (self-hosted), liczbowym identyfikatorem projektu i innym
 * uwierzytelnianiem webhooka.
 */

export type ScmEventStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';

export interface ScmRepoOption {
  fullName: string;
  name: string;
  private: boolean;
  defaultBranch: string;
  htmlUrl: string;
  cloneUrl: string;
  connected: boolean;
}

export interface ScmIntegration {
  id: string;
  provider: string;
  repoFullName: string;
  repoUrl: string;
  defaultBranch: string;
  projectId: string | null;
  webhookActive: boolean;
  isActive: boolean;
  createdAt: string;
  /** Adres instancji — wypełniony tylko dla GitLaba. */
  gitlabUrl: string | null;
}

/** Konfiguracja integracji z TestRailem (Story 8.8). */
export interface TestRailConfig {
  id: string;
  projectId: string;
  baseUrl: string;
  email: string;
  testrailProjectId: number | null;
  suiteId: number | null;
  priorityMap: Record<string, number>;
  typeMap: Record<string, number>;
  fieldMapping: Record<string, string>;
  isActive: boolean;
  createdAt: string;
}

export interface TestRailConfigPayload {
  baseUrl: string;
  email: string;
  apiKey: string;
  testrailProjectId: number;
  suiteId?: number | null;
  priorityMap?: Record<string, number> | null;
  typeMap?: Record<string, number> | null;
  fieldMapping?: Record<string, string> | null;
}

export interface TestRailConnectionResult {
  connected: boolean;
  message: string;
  projectName: string | null;
}

export interface TmsExportAccepted {
  taskId: string;
  status: string;
  statusUrl: string;
  testCases: number;
}

/** Konfiguracja integracji z Jirą przez wtyczkę testową (Story 8.9). */
export type JiraPlugin = 'xray' | 'zephyr';

export interface JiraTmsConfig {
  id: string;
  projectId: string;
  baseUrl: string;
  email: string;
  projectKey: string;
  plugin: JiraPlugin;
  linkedIssue: string | null;
  priorityMap: Record<string, string>;
  typeLabels: Record<string, string>;
  isActive: boolean;
  createdAt: string;
}

export interface JiraTmsConfigPayload {
  baseUrl: string;
  email: string;
  apiToken: string;
  projectKey: string;
  plugin: JiraPlugin;
  linkedIssue?: string | null;
  priorityMap?: Record<string, string> | null;
  typeLabels?: Record<string, string> | null;
}

export interface JiraTmsConnectionResult {
  connected: boolean;
  message: string;
  projectName: string | null;
  account: string | null;
}

/** Konfiguracja status checka per integracja (Story 8.3). */
export interface StatusCheckConfig {
  integrationId: string;
  severityThreshold: 'critical' | 'high' | 'medium';
  postComment: boolean;
  failOnThreshold: boolean;
  /** Nazwa do wpisania w regułach ochrony gałęzi. */
  statusContext: string;
}

export interface StatusCheckConfigUpdate {
  severityThreshold: 'critical' | 'high' | 'medium';
  postComment: boolean;
  failOnThreshold: boolean;
}

/** Projekt GitLab dostępny dla autoryzacji (Story 8.2). */
export interface GitLabProjectOption {
  projectId: number;
  pathWithNamespace: string;
  name: string;
  visibility: string;
  defaultBranch: string;
  webUrl: string;
  httpUrlToRepo: string;
  connected: boolean;
}

export interface ScmIntegrationList {
  items: ScmIntegration[];
  total: number;
  /** false ⇒ serwer nie ma skonfigurowanej aplikacji OAuth. */
  providerConfigured: boolean;
}

export interface IntegrationEvent {
  id: string;
  eventType: string;
  action: string | null;
  repoFullName: string;
  branch: string | null;
  baseBranch: string | null;
  commitSha: string | null;
  prNumber: number | null;
  status: ScmEventStatus;
  taskId: string | null;
  errorMessage: string | null;
  createdAt: string;
  completedAt: string | null;
}

// ── Synchronizacja dwukierunkowa z TMS (Story 8.11) ─────────────────────────

export type SyncDirection = 'push' | 'pull' | 'bidirectional';
export type ConflictStrategy = 'last_write_wins' | 'manual';
export type SyncHealth = 'active' | 'degraded';
export type ConflictResolution = 'pending' | 'testgen_wins' | 'tms_wins' | 'manual';

export interface SyncConfigPayload {
  direction: SyncDirection;
  intervalMinutes: number;
  conflictStrategy: ConflictStrategy;
}

export interface SyncStatus {
  id: string;
  integrationId: string;
  projectId: string;
  provider: string;
  direction: SyncDirection;
  conflictStrategy: ConflictStrategy;
  intervalMinutes: number;
  isActive: boolean;
  health: SyncHealth;
  lastSyncAt: string | null;
  lastSyncStatus: string | null;
  lastError: string | null;
  consecutiveFailures: number;
  syncedCount: number;
  pendingConflicts: number;
  nextSyncAt: string | null;
}

export interface SyncRunAccepted {
  syncStateId: string;
  taskId: string | null;
  status: string;
  statusUrl: string | null;
}

export interface SyncConflict {
  id: string;
  syncStateId: string;
  testCaseId: string;
  tmsTestId: string;
  testgenVersion: Record<string, unknown>;
  tmsVersion: Record<string, unknown>;
  resolution: ConflictResolution;
  resolvedAt: string | null;
  resolvedBy: string | null;
  createdAt: string | null;
}

export interface SyncConflictList {
  items: SyncConflict[];
  total: number;
}

// ── Import wymagań z Jiry (Story 8.12) ──────────────────────────────────────

export type JiraImportStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface JiraProjectOption {
  key: string;
  name: string;
}

export interface JiraProjectList {
  items: JiraProjectOption[];
  total: number;
}

export interface JiraImportPayload {
  jiraProjectKey: string;
  issueTypes: string[];
  updatedAfter?: string | null;
  fullReimport?: boolean;
}

export interface JiraImportAccepted {
  importId: string;
  taskId: string | null;
  status: string;
  statusUrl: string | null;
}

export interface JiraImportState {
  id: string;
  projectId: string;
  integrationId: string;
  jiraProjectKey: string;
  issueTypes: string[];
  status: JiraImportStatus;
  lastImportAt: string | null;
  totalImported: number;
  totalAttachments: number;
  totalSkipped: number;
  lastError: string | null;
  taskId: string | null;
  documentFileId: string | null;
  createdAt: string | null;
}

@Injectable({ providedIn: 'root' })
export class IntegrationService {
  private readonly apiUrl = `${environment.apiUrl}/integrations/github`;
  private readonly gitlabUrl = `${environment.apiUrl}/integrations/gitlab`;
  private readonly http = inject(HttpClient);

  readonly integrationsSignal = signal<ScmIntegration[]>([]);
  readonly providerConfiguredSignal = signal(true);
  readonly eventsSignal = signal<IntegrationEvent[]>([]);
  readonly isLoadingSignal = signal(false);

  readonly gitlabIntegrationsSignal = signal<ScmIntegration[]>([]);
  readonly gitlabConfiguredSignal = signal(true);
  readonly gitlabEventsSignal = signal<IntegrationEvent[]>([]);
  readonly isLoadingGitlabSignal = signal(false);

  /** Stan synchronizacji z TMS i jej konflikty (Story 8.11). */
  readonly syncStatusSignal = signal<SyncStatus | null>(null);
  readonly syncConflictsSignal = signal<SyncConflict[]>([]);

  /** Stan importów z Jiry dla bieżącego projektu (Story 8.12). */
  readonly jiraImportsSignal = signal<JiraImportState[]>([]);

  /** Adres autoryzacji GitHuba — nawigację wykonuje komponent. */
  getGitHubAuthUrl(): Observable<{ authorizationUrl: string }> {
    return this.http.get<{ authorizationUrl: string }>(`${this.apiUrl}/authorize`);
  }

  getConnectedRepos(): Observable<ScmIntegrationList> {
    this.isLoadingSignal.set(true);
    return this.http.get<ScmIntegrationList>(`${this.apiUrl}/repos`).pipe(
      tap({
        next: (result) => {
          this.integrationsSignal.set(result.items ?? []);
          this.providerConfiguredSignal.set(result.providerConfigured !== false);
          this.isLoadingSignal.set(false);
        },
        error: () => this.isLoadingSignal.set(false),
      }),
    );
  }

  getAvailableRepos(): Observable<ScmRepoOption[]> {
    return this.http.get<ScmRepoOption[]>(`${this.apiUrl}/available-repos`);
  }

  connectRepo(fullName: string): Observable<ScmIntegration> {
    return this.http.post<ScmIntegration>(`${this.apiUrl}/repos`, { fullName });
  }

  removeIntegration(integrationId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/repos/${integrationId}`);
  }

  getRecentEvents(integrationId?: string, limit = 10): Observable<IntegrationEvent[]> {
    let params = new HttpParams().set('limit', String(limit));
    if (integrationId) {
      params = params.set('integration_id', integrationId);
    }
    return this.http
      .get<IntegrationEvent[]>(`${this.apiUrl}/events`, { params })
      .pipe(tap((events) => this.eventsSignal.set(events ?? [])));
  }

  // ── GitLab (Story 8.2) ────────────────────────────────────────────────────

  /**
   * Adres autoryzacji wskazanej instancji GitLab.
   *
   * `gitlabUrl` przekazujemy dalej, bo ta sama aplikacja OAuth obsługuje
   * gitlab.com i instancje self-hosted — backend zapamięta go w `state`.
   */
  getGitLabAuthUrl(gitlabUrl?: string): Observable<{ authorizationUrl: string }> {
    const params = gitlabUrl ? new HttpParams().set('gitlab_url', gitlabUrl) : undefined;
    return this.http.get<{ authorizationUrl: string }>(`${this.gitlabUrl}/authorize`, { params });
  }

  getGitLabProjects(): Observable<ScmIntegrationList> {
    this.isLoadingGitlabSignal.set(true);
    return this.http.get<ScmIntegrationList>(`${this.gitlabUrl}/projects`).pipe(
      tap({
        next: (result) => {
          this.gitlabIntegrationsSignal.set(result.items ?? []);
          this.gitlabConfiguredSignal.set(result.providerConfigured !== false);
          this.isLoadingGitlabSignal.set(false);
        },
        error: () => this.isLoadingGitlabSignal.set(false),
      }),
    );
  }

  getAvailableGitLabProjects(gitlabUrl?: string): Observable<GitLabProjectOption[]> {
    const params = gitlabUrl ? new HttpParams().set('gitlab_url', gitlabUrl) : undefined;
    return this.http.get<GitLabProjectOption[]>(`${this.gitlabUrl}/available-projects`, { params });
  }

  connectGitLabProject(projectId: number, gitlabUrl?: string): Observable<ScmIntegration> {
    const params = gitlabUrl ? new HttpParams().set('gitlab_url', gitlabUrl) : undefined;
    return this.http.post<ScmIntegration>(`${this.gitlabUrl}/projects`, { projectId }, { params });
  }

  removeGitLabIntegration(integrationId: string): Observable<void> {
    return this.http.delete<void>(`${this.gitlabUrl}/projects/${integrationId}`);
  }

  getGitLabRecentEvents(integrationId?: string, limit = 10): Observable<IntegrationEvent[]> {
    let params = new HttpParams().set('limit', String(limit));
    if (integrationId) {
      params = params.set('integration_id', integrationId);
    }
    return this.http
      .get<IntegrationEvent[]>(`${this.gitlabUrl}/events`, { params })
      .pipe(tap((events) => this.gitlabEventsSignal.set(events ?? [])));
  }

  // ── status checki (Story 8.3) ─────────────────────────────────────────────

  /** Konfiguracja wspólna dla obu dostawców — adresowana po id integracji. */
  getStatusCheckConfig(integrationId: string): Observable<StatusCheckConfig> {
    return this.http.get<StatusCheckConfig>(`${environment.apiUrl}/integrations/${integrationId}/config`);
  }

  updateStatusCheckConfig(integrationId: string, config: StatusCheckConfigUpdate): Observable<StatusCheckConfig> {
    return this.http.put<StatusCheckConfig>(`${environment.apiUrl}/integrations/${integrationId}/config`, config);
  }

  // ── TestRail (Story 8.8) ──────────────────────────────────────────────────

  /**
   * Konfiguracja TestRaila jest per projekt, bo identyfikator projektu
   * docelowego różni się między projektami TestGEN — stąd `projectId`
   * w parametrach, mimo że endpoint żyje pod `/integrations`.
   */
  getTestRailConfig(projectId: string): Observable<TestRailConfig> {
    return this.http.get<TestRailConfig>(`${environment.apiUrl}/integrations/testrail/config`, {
      params: new HttpParams().set('project_id', projectId),
    });
  }

  saveTestRailConfig(projectId: string, payload: TestRailConfigPayload): Observable<TestRailConfig> {
    return this.http.put<TestRailConfig>(`${environment.apiUrl}/integrations/testrail/config`, payload, {
      params: new HttpParams().set('project_id', projectId),
    });
  }

  testTestRailConnection(projectId: string): Observable<TestRailConnectionResult> {
    return this.http.post<TestRailConnectionResult>(
      `${environment.apiUrl}/integrations/testrail/test`,
      {},
      { params: new HttpParams().set('project_id', projectId) },
    );
  }

  /** Pusta lista `testCaseIds` oznacza wszystkie przypadki projektu. */
  exportToTestRail(projectId: string, testCaseIds: string[] = []): Observable<TmsExportAccepted> {
    return this.http.post<TmsExportAccepted>(`${environment.apiUrl}/projects/${projectId}/export/testrail`, {
      testCaseIds,
    });
  }

  // ── Jira Xray / Zephyr Scale (Story 8.9) ──────────────────────────────────

  getJiraTmsConfig(projectId: string): Observable<JiraTmsConfig> {
    return this.http.get<JiraTmsConfig>(`${environment.apiUrl}/integrations/jira/config`, {
      params: new HttpParams().set('project_id', projectId),
    });
  }

  saveJiraTmsConfig(projectId: string, payload: JiraTmsConfigPayload): Observable<JiraTmsConfig> {
    return this.http.put<JiraTmsConfig>(`${environment.apiUrl}/integrations/jira/config`, payload, {
      params: new HttpParams().set('project_id', projectId),
    });
  }

  testJiraTmsConnection(projectId: string): Observable<JiraTmsConnectionResult> {
    return this.http.post<JiraTmsConnectionResult>(
      `${environment.apiUrl}/integrations/jira/test`,
      {},
      { params: new HttpParams().set('project_id', projectId) },
    );
  }

  /**
   * Eksport do wtyczki zgodnej z konfiguracją projektu.
   *
   * Wtyczka jest częścią adresu, bo backend odrzuca eksport niezgodny
   * z zapisaną konfiguracją — nie chcemy po cichu wysłać testów nie tam.
   */
  exportToJiraTms(projectId: string, plugin: JiraPlugin, testCaseIds: string[] = []): Observable<TmsExportAccepted> {
    return this.http.post<TmsExportAccepted>(`${environment.apiUrl}/projects/${projectId}/export/${plugin}`, {
      testCaseIds,
    });
  }

  // ── Synchronizacja dwukierunkowa (Story 8.11) ─────────────────────────────

  /**
   * Konfiguracja synchronizacji nie uruchamia jej — do tego służy
   * `activateSync`. Rozdzielenie jest celowe: zapis ustawień nie może
   * po cichu zacząć wysyłać przypadków do TMS-a.
   */
  configureSync(integrationId: string, payload: SyncConfigPayload): Observable<SyncStatus> {
    return this.http.put<SyncStatus>(`${environment.apiUrl}/integrations/${integrationId}/sync/config`, payload);
  }

  getSyncStatus(integrationId: string): Observable<SyncStatus> {
    return this.http
      .get<SyncStatus>(`${environment.apiUrl}/integrations/${integrationId}/sync/status`)
      .pipe(tap((status) => this.syncStatusSignal.set(status)));
  }

  activateSync(integrationId: string): Observable<SyncStatus> {
    return this.http
      .post<SyncStatus>(`${environment.apiUrl}/integrations/${integrationId}/sync/activate`, {})
      .pipe(tap((status) => this.syncStatusSignal.set(status)));
  }

  deactivateSync(integrationId: string): Observable<SyncStatus> {
    return this.http
      .post<SyncStatus>(`${environment.apiUrl}/integrations/${integrationId}/sync/deactivate`, {})
      .pipe(tap((status) => this.syncStatusSignal.set(status)));
  }

  runSyncNow(integrationId: string): Observable<SyncRunAccepted> {
    return this.http.post<SyncRunAccepted>(`${environment.apiUrl}/integrations/${integrationId}/sync/run`, {});
  }

  getSyncConflicts(integrationId: string, resolution?: ConflictResolution): Observable<SyncConflictList> {
    let params = new HttpParams();
    if (resolution) {
      params = params.set('resolution', resolution);
    }
    return this.http
      .get<SyncConflictList>(`${environment.apiUrl}/integrations/${integrationId}/sync/conflicts`, { params })
      .pipe(tap((list) => this.syncConflictsSignal.set(list.items ?? [])));
  }

  resolveSyncConflict(conflictId: string, resolution: ConflictResolution): Observable<SyncConflict> {
    return this.http.post<SyncConflict>(`${environment.apiUrl}/sync/conflicts/${conflictId}/resolve`, {
      resolution,
    });
  }

  // ── Import wymagań z Jiry (Story 8.12) ────────────────────────────────────

  getJiraProjects(projectId: string): Observable<JiraProjectList> {
    return this.http.get<JiraProjectList>(`${environment.apiUrl}/projects/${projectId}/import/jira/projects`);
  }

  importFromJira(projectId: string, payload: JiraImportPayload): Observable<JiraImportAccepted> {
    return this.http.post<JiraImportAccepted>(`${environment.apiUrl}/projects/${projectId}/import/jira`, payload);
  }

  getJiraImportStatus(projectId: string): Observable<JiraImportState[]> {
    return this.http
      .get<JiraImportState[]>(`${environment.apiUrl}/projects/${projectId}/import/jira/status`)
      .pipe(tap((items) => this.jiraImportsSignal.set(items ?? [])));
  }
}
