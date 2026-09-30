import { HttpClient } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, tap } from "rxjs";
import { environment } from "../../../environments/environment";

export interface ProjectDashboardItem {
  id: string;
  name: string;
  lastAnalysisAt: string | null;
  complianceScore: number | null;
  testCasesCount: number;
  status: string;
}

export interface StatisticsCards {
  totalProjects: number;
  analysesThisMonth: number;
  avgCompliance: number | null;
  /** Story 6.1 AC2 — 4. karta statystyki. */
  totalTestCases: number;
  /** Utrzymujemy dla zgodności z BE; FE nie renderuje jako karty. */
  activeUsers: number;
}

export interface PlanUsage {
  plan: string;
  analysesUsed: number;
  /** null = unlimited (plan Premium, Story 7.1). */
  analysesLimit: number | null;
  projectsCount: number;
}

export interface AuditLogEntry {
  id: string;
  userId: string | null;
  action: string;
  resourceType: string | null;
  resourceId: string | null;
  details: Record<string, unknown> | null;
  createdAt: string;
  userEmail: string | null;
}

export interface AuditLogList {
  items: AuditLogEntry[];
  total: number;
}

export interface DashboardSummary {
  projects: ProjectDashboardItem[];
  statistics: StatisticsCards;
  planUsage: PlanUsage | null;
}

/**
 * HTTP + signal state for the main dashboard (Story 6.1).
 *
 * Single round-trip for summary via /dashboard/summary;
 * activity feed polls /dashboard/audit-logs every 30s (rxjs interval
 * subscribed by the component so polling stops on destroy).
 */
@Injectable({ providedIn: "root" })
export class DashboardService {
  private readonly apiUrl = `${environment.apiUrl}/dashboard`;
  private readonly http = inject(HttpClient);

  readonly projectsSignal = signal<ProjectDashboardItem[]>([]);
  readonly statisticsSignal = signal<StatisticsCards | null>(null);
  readonly planUsageSignal = signal<PlanUsage | null>(null);
  readonly activitySignal = signal<AuditLogEntry[]>([]);
  readonly isLoadingSummarySignal = signal(false);
  readonly isLoadingActivitySignal = signal(false);
  readonly errorSignal = signal<string | null>(null);

  loadSummary(): Observable<DashboardSummary> {
    this.isLoadingSummarySignal.set(true);
    // Kasujemy poprzedni błąd już przy starcie, żeby ponowna próba dawała
    // widoczną reakcję zamiast zostawiać stary komunikat do czasu odpowiedzi.
    this.errorSignal.set(null);
    return this.http.get<DashboardSummary>(`${this.apiUrl}/summary`).pipe(
      tap({
        next: (data) => {
          this.projectsSignal.set(data.projects);
          this.statisticsSignal.set(data.statistics);
          this.planUsageSignal.set(data.planUsage);
          this.isLoadingSummarySignal.set(false);
          this.errorSignal.set(null);
        },
        error: () => {
          this.isLoadingSummarySignal.set(false);
          this.errorSignal.set("Nie udało się pobrać danych dashboardu.");
        },
      }),
    );
  }

  loadActivity(limit = 20): Observable<AuditLogList> {
    this.isLoadingActivitySignal.set(true);
    return this.http
      .get<AuditLogList>(`${this.apiUrl}/audit-logs`, {
        params: { limit: String(limit) },
      })
      .pipe(
        tap({
          next: (data) => {
            this.activitySignal.set(data.items);
            this.isLoadingActivitySignal.set(false);
          },
          error: () => this.isLoadingActivitySignal.set(false),
        }),
      );
  }
}
