import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, tap } from "rxjs";

import { environment } from "../../../../environments/environment";

export interface AdminUser {
  id: string;
  tenantId: string | null;
  email: string;
  name: string | null;
  role: string;
  isActive: boolean;
  isBlocked: boolean;
  deletedAt: string | null;
  createdAt: string | null;
  lastLoginAt: string | null;
}

export interface AdminUserList {
  users: AdminUser[];
  total: number;
}

export interface UserFilters {
  page?: number;
  pageSize?: number;
  tenantId?: string;
  search?: string;
  role?: string;
}

export interface CreateUserRequest {
  email: string;
  role: string;
}

export interface InviteResponse {
  message: string;
  userId: string;
}

export interface AdminTenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  isActive: boolean;
  createdAt: string | null;
  userCount: number;
  storageBytes: number;
  projectCount: number;
}

export interface AdminTenantList {
  tenants: AdminTenant[];
  total: number;
}

export interface TenantFilters {
  page?: number;
  pageSize?: number;
  search?: string;
}

export interface AdminTenantProject {
  id: string;
  name: string;
  status: string;
  createdAt: string | null;
}

export interface AdminTenantProjectList {
  projects: AdminTenantProject[];
  total: number;
}

export interface AdminAuditLogEntry {
  id: string;
  createdAt: string;
  tenantId: string | null;
  userId: string | null;
  action: string;
  resourceType: string;
  resourceId: string;
  details: Record<string, unknown> | null;
  ipAddress: string | null;
}

export interface AdminAuditLogList {
  logs: AdminAuditLogEntry[];
  total: number;
}

export interface AuditLogFilters {
  page?: number;
  pageSize?: number;
  dateFrom?: string;
  dateTo?: string;
  userId?: string;
  tenantId?: string;
  action?: string;
  resourceType?: string;
}

export interface PlatformLimits {
  maxFileSizeMb: number;
  maxProjectsPerTenant: number;
  maxUsersPerTenant: number;
  llmCostLimitUsd: number;
}

export interface PlatformLlm {
  provider: string;
  model: string;
  temperature: number;
  maxTokens: number;
  timeoutSeconds: number;
}

export interface PlatformMaintenance {
  enabled: boolean;
  message: string;
}

export interface PlatformConfig {
  limits: PlatformLimits;
  llm: PlatformLlm;
  maintenance: PlatformMaintenance;
  featureFlags: Record<string, boolean>;
}

export interface PlatformConfigUpdate {
  limits?: Partial<PlatformLimits>;
  llm?: Partial<PlatformLlm>;
  maintenance?: Partial<PlatformMaintenance>;
  featureFlags?: Record<string, boolean>;
}

/**
 * HTTP + stan sygnałowy panelu administracyjnego (Story 6.15).
 *
 * Klucze parametrów zapytań podawane są w snake_case — interceptor
 * `snakeCaseInterceptor` konwertuje wyłącznie ciała żądań i odpowiedzi,
 * nie dotyka query stringa.
 */
@Injectable({ providedIn: "root" })
export class AdminService {
  private readonly apiUrl = environment.apiUrl;
  private readonly http = inject(HttpClient);

  readonly usersSignal = signal<AdminUser[]>([]);
  readonly usersTotalSignal = signal(0);
  readonly tenantsSignal = signal<AdminTenant[]>([]);
  readonly tenantsTotalSignal = signal(0);
  readonly selectedTenantSignal = signal<AdminTenant | null>(null);
  readonly tenantProjectsSignal = signal<AdminTenantProject[]>([]);
  readonly tenantProjectsTotalSignal = signal(0);
  readonly auditLogSignal = signal<AdminAuditLogEntry[]>([]);
  readonly auditLogTotalSignal = signal(0);
  readonly auditActionsSignal = signal<string[]>([]);
  readonly configSignal = signal<PlatformConfig | null>(null);
  readonly isLoadingSignal = signal(false);
  readonly errorSignal = signal<string | null>(null);

  getUsers(filters: UserFilters = {}): Observable<AdminUserList> {
    this.startRequest();
    const params = this.toParams({
      page: filters.page ?? 1,
      page_size: filters.pageSize,
      tenant_id: filters.tenantId,
      search: filters.search,
      role: filters.role,
    });
    return this.http.get<AdminUserList>(`${this.apiUrl}/users`, { params }).pipe(
      tap({
        next: (data) => {
          this.usersSignal.set(data.users);
          this.usersTotalSignal.set(data.total);
          this.finishRequest();
        },
        error: () => this.failRequest("Nie udało się pobrać listy użytkowników."),
      }),
    );
  }

  createUser(payload: CreateUserRequest): Observable<InviteResponse> {
    this.startRequest();
    return this.http
      .post<InviteResponse>(`${this.apiUrl}/users/invite`, payload)
      .pipe(
        tap({
          next: () => this.finishRequest(),
          error: () => this.failRequest("Nie udało się zaprosić użytkownika."),
        }),
      );
  }

  updateUserRole(userId: string, role: string): Observable<AdminUser> {
    this.startRequest();
    return this.http
      .put<AdminUser>(`${this.apiUrl}/users/${userId}/role`, { role })
      .pipe(
        tap({
          next: (user) => {
            this.replaceUser(user);
            this.finishRequest();
          },
          error: () => this.failRequest("Nie udało się zmienić roli użytkownika."),
        }),
      );
  }

  blockUser(userId: string): Observable<AdminUser> {
    return this.setBlocked(userId, "block", "Nie udało się zablokować użytkownika.");
  }

  unblockUser(userId: string): Observable<AdminUser> {
    return this.setBlocked(userId, "unblock", "Nie udało się odblokować użytkownika.");
  }

  deleteUser(userId: string): Observable<void> {
    this.startRequest();
    return this.http.delete<void>(`${this.apiUrl}/users/${userId}`).pipe(
      tap({
        next: () => {
          this.usersSignal.update((users) => users.filter((user) => user.id !== userId));
          this.usersTotalSignal.update((total) => Math.max(total - 1, 0));
          this.finishRequest();
        },
        error: () => this.failRequest("Nie udało się usunąć użytkownika."),
      }),
    );
  }

  getTenants(filters: TenantFilters = {}): Observable<AdminTenantList> {
    this.startRequest();
    const params = this.toParams({
      page: filters.page ?? 1,
      page_size: filters.pageSize,
      search: filters.search,
    });
    return this.http
      .get<AdminTenantList>(`${this.apiUrl}/admin/tenants`, { params })
      .pipe(
        tap({
          next: (data) => {
            this.tenantsSignal.set(data.tenants);
            this.tenantsTotalSignal.set(data.total);
            this.finishRequest();
          },
          error: () => this.failRequest("Nie udało się pobrać listy tenantów."),
        }),
      );
  }

  getTenantDetails(tenantId: string): Observable<AdminTenant> {
    this.startRequest();
    return this.http
      .get<AdminTenant>(`${this.apiUrl}/admin/tenants/${tenantId}`)
      .pipe(
        tap({
          next: (tenant) => {
            this.selectedTenantSignal.set(tenant);
            this.finishRequest();
          },
          error: () => this.failRequest("Nie udało się pobrać szczegółów tenanta."),
        }),
      );
  }

  getTenantProjects(
    tenantId: string,
    filters: TenantFilters = {},
  ): Observable<AdminTenantProjectList> {
    this.startRequest();
    const params = this.toParams({
      page: filters.page ?? 1,
      page_size: filters.pageSize,
    });
    return this.http
      .get<AdminTenantProjectList>(`${this.apiUrl}/admin/tenants/${tenantId}/projects`, {
        params,
      })
      .pipe(
        tap({
          next: (data) => {
            this.tenantProjectsSignal.set(data.projects);
            this.tenantProjectsTotalSignal.set(data.total);
            this.finishRequest();
          },
          error: () => this.failRequest("Nie udało się pobrać projektów tenanta."),
        }),
      );
  }

  getAuditLog(filters: AuditLogFilters = {}): Observable<AdminAuditLogList> {
    this.startRequest();
    const params = this.toParams({
      page: filters.page ?? 1,
      page_size: filters.pageSize,
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
      user_id: filters.userId,
      tenant_id: filters.tenantId,
      action: filters.action,
      resource_type: filters.resourceType,
    });
    return this.http
      .get<AdminAuditLogList>(`${this.apiUrl}/admin/audit-logs`, { params })
      .pipe(
        tap({
          next: (data) => {
            this.auditLogSignal.set(data.logs);
            this.auditLogTotalSignal.set(data.total);
            this.finishRequest();
          },
          error: () => this.failRequest("Nie udało się pobrać logu audytu."),
        }),
      );
  }

  getAuditActions(): Observable<string[]> {
    return this.http
      .get<string[]>(`${this.apiUrl}/admin/audit-logs/actions`)
      .pipe(tap((actions) => this.auditActionsSignal.set(actions)));
  }

  getConfig(): Observable<PlatformConfig> {
    this.startRequest();
    return this.http.get<PlatformConfig>(`${this.apiUrl}/admin/config`).pipe(
      tap({
        next: (config) => {
          this.configSignal.set(config);
          this.finishRequest();
        },
        error: () => this.failRequest("Nie udało się pobrać konfiguracji platformy."),
      }),
    );
  }

  updateConfig(sections: PlatformConfigUpdate): Observable<PlatformConfig> {
    this.startRequest();
    return this.http
      .put<PlatformConfig>(`${this.apiUrl}/admin/config`, sections)
      .pipe(
        tap({
          next: (config) => {
            this.configSignal.set(config);
            this.finishRequest();
          },
          error: () => this.failRequest("Nie udało się zapisać konfiguracji platformy."),
        }),
      );
  }

  private setBlocked(
    userId: string,
    action: "block" | "unblock",
    errorMessage: string,
  ): Observable<AdminUser> {
    this.startRequest();
    return this.http
      .post<AdminUser>(`${this.apiUrl}/users/${userId}/${action}`, {})
      .pipe(
        tap({
          next: (user) => {
            this.replaceUser(user);
            this.finishRequest();
          },
          error: () => this.failRequest(errorMessage),
        }),
      );
  }

  private replaceUser(updated: AdminUser): void {
    this.usersSignal.update((users) =>
      users.map((user) => (user.id === updated.id ? updated : user)),
    );
  }

  /** Pomija filtry puste i niezdefiniowane — inaczej backend odrzuciłby pusty ciąg. */
  private toParams(values: Record<string, string | number | undefined>): HttpParams {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(values)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }
      params = params.set(key, String(value));
    }
    return params;
  }

  private startRequest(): void {
    this.isLoadingSignal.set(true);
    this.errorSignal.set(null);
  }

  private finishRequest(): void {
    this.isLoadingSignal.set(false);
    this.errorSignal.set(null);
  }

  private failRequest(message: string): void {
    this.isLoadingSignal.set(false);
    this.errorSignal.set(message);
  }
}
