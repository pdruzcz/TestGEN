import { Injectable, computed, inject, signal } from "@angular/core";
import { Observable, forkJoin, of } from "rxjs";
import { catchError, map, tap } from "rxjs/operators";
import {
  GapAnalysisService,
  GapAnalysisSummary,
  GapFinding,
} from "../../gap-analysis/services/gap-analysis.service";
import {
  SecurityFinding,
  SecurityReport,
  SecurityScanService,
} from "../../projects/security/services/security-scan.service";
import { TestCaseService } from "../../test-cases/services/test-case.service";
import { HttpClient } from "@angular/common/http";
import { environment } from "../../../../environments/environment";

/** Znormalizowana severity (AC7) — krytyczny/wysoki/średni/niski. */
export type ResultSeverity = "critical" | "high" | "medium" | "low";

/** Znormalizowany status wyniku (AC2) — nowy/zaakceptowany/odrzucony. */
export type ResultStatus = "new" | "accepted" | "rejected";

export type ResultSource = "security" | "gap";

/** Ujednolicony wynik analizy prezentowany w przeglądarce wyników (Story 6.4). */
export interface ResultItem {
  id: string;
  source: ResultSource;
  title: string;
  description: string;
  severity: ResultSeverity;
  type: string;
  filePath: string | null;
  module: string | null;
  status: ResultStatus;
  codeSnippet: string | null;
  language: string | null;
  lineStart: number | null;
  suggestedFix: string | null;
}

export interface ResultsFilters {
  severities: ResultSeverity[];
  type: string | null;
  file: string | null;
  module: string | null;
  status: ResultStatus | null;
}

export interface ResultsSort {
  column: "title" | "severity" | "type" | "filePath" | "status";
  direction: "asc" | "desc";
}

export interface ComplianceScore {
  score: number;
  totalFindings: number;
  breakdown: Record<string, number>;
}

export interface ModuleScore {
  filePath: string;
  score: number;
  totalFindings: number;
  breakdown: Record<string, number>;
}

export const EMPTY_FILTERS: ResultsFilters = {
  severities: [],
  type: null,
  file: null,
  module: null,
  status: null,
};

const SEVERITY_ORDER: Record<ResultSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

/** Mapuje severity BE (security: critical..info, gap: critical/warning/info) na skalę AC7. */
export function normalizeSeverity(
  raw: string | null | undefined,
): ResultSeverity {
  switch ((raw ?? "").toLowerCase()) {
    case "critical":
      return "critical";
    case "high":
      return "high";
    case "medium":
    case "warning":
      return "medium";
    default:
      return "low";
  }
}

/** Mapuje status triage security (open/acknowledged/fixed/false_positive) na nowy/zaakceptowany/odrzucony. */
export function normalizeStatus(raw: string | null | undefined): ResultStatus {
  switch ((raw ?? "").toLowerCase()) {
    case "acknowledged":
    case "fixed":
      return "accepted";
    case "false_positive":
      return "rejected";
    default:
      return "new";
  }
}

function moduleFromPath(filePath: string | null): string | null {
  if (!filePath) return null;
  const normalized = filePath.replace(/\\/g, "/");
  const idx = normalized.indexOf("/");
  return idx > 0 ? normalized.slice(0, idx) : normalized;
}

function languageFromPath(filePath: string | null): string | null {
  if (!filePath) return null;
  const ext = filePath.split(".").pop()?.toLowerCase() ?? "";
  const mapping: Record<string, string> = {
    py: "python",
    java: "java",
    js: "javascript",
    jsx: "javascript",
    ts: "typescript",
    tsx: "typescript",
    sql: "sql",
  };
  return mapping[ext] ?? null;
}

function toSecurityItem(f: SecurityFinding): ResultItem {
  return {
    id: f.id,
    source: "security",
    title: f.vulnerabilityType,
    description: f.description,
    severity: normalizeSeverity(f.severity),
    type: f.scanType,
    filePath: f.filePath,
    module: moduleFromPath(f.filePath),
    status: normalizeStatus(f.status),
    codeSnippet: f.codeSnippet,
    language: languageFromPath(f.filePath),
    lineStart: f.lineStart,
    suggestedFix: null,
  };
}

function toGapItem(f: GapFinding): ResultItem {
  return {
    id: f.id,
    source: "gap",
    title: f.description || `Luka: ${f.gapType}`,
    description: f.requirementText ?? f.description,
    severity: normalizeSeverity(f.severity),
    type: f.gapType,
    filePath: f.codeReference,
    module: moduleFromPath(f.codeReference),
    status: "new",
    codeSnippet: null,
    language: f.skeletonLanguage,
    lineStart: null,
    suggestedFix: f.skeletonCode,
  };
}

/**
 * Agreguje wyniki analiz z istniejących endpointów BE (security-findings,
 * gap-findings, compliance) w jeden ujednolicony model dla przeglądarki
 * wyników. Filtry, wyszukiwanie i sortowanie realizowane po stronie FE
 * na signals/computed (Story 6.4).
 */
@Injectable({ providedIn: "root" })
export class ResultsService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;
  private readonly securityService = inject(SecurityScanService);
  private readonly gapService = inject(GapAnalysisService);
  readonly testCaseService = inject(TestCaseService);

  // --- State signals ---
  readonly resultsSignal = signal<ResultItem[]>([]);
  readonly filtersSignal = signal<ResultsFilters>(EMPTY_FILTERS);
  readonly searchQuerySignal = signal("");
  readonly sortSignal = signal<ResultsSort>({
    column: "severity",
    direction: "asc",
  });
  readonly activeTabSignal = signal(0);
  readonly isLoadingSignal = signal(false);

  // --- Overview data ---
  readonly gapSummarySignal = signal<GapAnalysisSummary | null>(null);
  readonly complianceSignal = signal<ComplianceScore | null>(null);
  readonly moduleScoresSignal = signal<ModuleScore[]>([]);
  readonly securityReportSignal = signal<SecurityReport | null>(null);

  /** AC2 + AC4 — filtry i wyszukiwanie pełnotekstowe po tytule i opisie. */
  readonly filteredResultsComputed = computed<ResultItem[]>(() => {
    const filters = this.filtersSignal();
    const query = this.searchQuerySignal().trim().toLowerCase();
    return this.resultsSignal().filter((item) => {
      if (
        filters.severities.length > 0 &&
        !filters.severities.includes(item.severity)
      ) {
        return false;
      }
      if (filters.type && item.type !== filters.type) return false;
      if (
        filters.file &&
        !(item.filePath ?? "")
          .toLowerCase()
          .includes(filters.file.toLowerCase())
      ) {
        return false;
      }
      if (filters.module && item.module !== filters.module) return false;
      if (filters.status && item.status !== filters.status) return false;
      if (
        query &&
        !item.title.toLowerCase().includes(query) &&
        !item.description.toLowerCase().includes(query)
      ) {
        return false;
      }
      return true;
    });
  });

  /** AC3 — sortowanie po kolumnie rosnąco/malejąco. */
  readonly sortedResultsComputed = computed<ResultItem[]>(() => {
    const { column, direction } = this.sortSignal();
    const factor = direction === "asc" ? 1 : -1;
    return [...this.filteredResultsComputed()].sort((a, b) => {
      let cmp: number;
      if (column === "severity") {
        cmp = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
      } else {
        cmp = String(a[column] ?? "").localeCompare(
          String(b[column] ?? ""),
          "pl",
        );
      }
      return cmp * factor;
    });
  });

  /** Unikalne wartości do zasilenia panelu filtrów. */
  readonly availableTypesComputed = computed(() =>
    [...new Set(this.resultsSignal().map((r) => r.type))].sort(),
  );
  readonly availableModulesComputed = computed(() =>
    [
      ...new Set(
        this.resultsSignal()
          .map((r) => r.module)
          .filter((m): m is string => !!m),
      ),
    ].sort(),
  );
  readonly availableFilesComputed = computed(() =>
    [
      ...new Set(
        this.resultsSignal()
          .map((r) => r.filePath)
          .filter((f): f is string => !!f),
      ),
    ].sort(),
  );

  /** Ładuje i scala wyniki security + gap dla projektu. */
  loadResults(projectId: string): Observable<ResultItem[]> {
    this.isLoadingSignal.set(true);
    return forkJoin({
      security: this.securityService
        .listFindings(projectId, { page: 1, pageSize: 200 })
        .pipe(
          catchError(() =>
            of({
              findings: [] as SecurityFinding[],
              total: 0,
              page: 1,
              pageSize: 200,
            }),
          ),
        ),
      gaps: this.gapService
        .getFindings(projectId, { page: 1, size: 100 })
        .pipe(catchError(() => of(null))),
    }).pipe(
      map(({ security, gaps }) => [
        ...security.findings.map(toSecurityItem),
        ...(gaps?.findings ?? []).map(toGapItem),
      ]),
      tap({
        next: (items) => {
          this.resultsSignal.set(items);
          this.isLoadingSignal.set(false);
        },
        error: () => this.isLoadingSignal.set(false),
      }),
    );
  }

  /** Dane zakładek Przegląd/Pokrycie/Raport — best-effort (błędy pojedynczych źródeł ignorowane). */
  loadOverview(projectId: string): void {
    this.gapService
      .getSummary(projectId)
      .pipe(catchError(() => of(null)))
      .subscribe((summary) => this.gapSummarySignal.set(summary));
    this.http
      .get<ComplianceScore>(`${this.apiUrl}/projects/${projectId}/compliance`)
      .pipe(catchError(() => of(null)))
      .subscribe((score) => this.complianceSignal.set(score));
    this.http
      .get<ModuleScore[]>(
        `${this.apiUrl}/projects/${projectId}/compliance/modules`,
      )
      .pipe(catchError(() => of([])))
      .subscribe((modules) => this.moduleScoresSignal.set(modules ?? []));
    this.securityService
      .getReport(projectId)
      .pipe(catchError(() => of(null)))
      .subscribe((report) => this.securityReportSignal.set(report));
    this.testCaseService
      .list({ projectId, page: 1, pageSize: 50 })
      .pipe(catchError(() => of(null)))
      .subscribe();
  }

  setFilters(filters: ResultsFilters): void {
    this.filtersSignal.set(filters);
  }

  setSearchQuery(query: string): void {
    this.searchQuerySignal.set(query);
  }

  toggleSort(column: ResultsSort["column"]): void {
    const current = this.sortSignal();
    this.sortSignal.set({
      column,
      direction:
        current.column === column && current.direction === "asc"
          ? "desc"
          : "asc",
    });
  }
}
