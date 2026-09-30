import { HttpClient } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, forkJoin, of, timer } from "rxjs";
import { catchError, concatMap, map, tap } from "rxjs/operators";
import { environment } from "../../../../environments/environment";
import {
  GapAnalysisService,
  GapAnalysisSummary,
  GapFinding,
  TrendPoint,
} from "../../gap-analysis/services/gap-analysis.service";
import {
  SecurityFinding,
  SecurityScanService,
} from "../../projects/security/services/security-scan.service";
import { TestCaseService } from "../../test-cases/services/test-case.service";
import {
  ComplianceScore,
  ModuleScore,
  ResultSeverity,
  normalizeSeverity,
} from "../../results/services/results.service";

export type ReportType = "executive" | "technical" | "both";

export type ReportStatus = "idle" | "generating" | "done" | "error";

/** AC7 — etapy generowania raportu widoczne na pasku postępu. */
export const REPORT_STAGES = [
  "Zbieranie danych",
  "Analiza trendów",
  "Generowanie treści",
  "Renderowanie",
] as const;

export interface ReportKpis {
  complianceScore: number | null;
  coveragePercentage: number | null;
  totalFindings: number;
  criticalCount: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  testCasesTotal: number;
  testCasesReady: number;
  testCasesPassed: number;
}

/** Ujednolicone ustalenie do raportu technicznego (AC3/AC5). */
export interface ReportFinding {
  id: string;
  source: "security" | "gap";
  title: string;
  description: string;
  severity: ResultSeverity;
  cweId: string | null;
  cvssScore: number | null;
  filePath: string | null;
  lineStart: number | null;
  codeSnippet: string | null;
  language: string | null;
  recommendation: string | null;
}

export interface ReportData {
  projectId: string;
  generatedAt: string;
  kpis: ReportKpis;
  severityCounts: Record<ResultSeverity, number>;
  moduleScores: ModuleScore[];
  trendPoints: TrendPoint[];
  conclusions: string[];
  findings: ReportFinding[];
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

function toReportFinding(f: SecurityFinding): ReportFinding {
  return {
    id: f.id,
    source: "security",
    title: f.vulnerabilityType,
    description: f.description,
    severity: normalizeSeverity(f.severity),
    cweId: f.cweId,
    cvssScore: f.cvssScore,
    filePath: f.filePath,
    lineStart: f.lineStart,
    codeSnippet: f.codeSnippet,
    language: languageFromPath(f.filePath),
    recommendation: f.recommendation,
  };
}

function gapToReportFinding(f: GapFinding): ReportFinding {
  return {
    id: f.id,
    source: "gap",
    title: f.description || `Luka: ${f.gapType}`,
    description: f.requirementText ?? f.description,
    severity: normalizeSeverity(f.severity),
    cweId: null,
    cvssScore: null,
    filePath: f.codeReference,
    lineStart: null,
    codeSnippet: f.skeletonCode,
    language: f.skeletonLanguage,
    recommendation: f.requirementText
      ? `Uzupełnić implementację wymagania: ${f.requirementText}`
      : null,
  };
}

const SEVERITY_ORDER: Record<ResultSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

/**
 * AC4 — wnioski executive summary: prosty polski język, bez żargonu
 * technicznego (bez CWE/CVE, nazw narzędzi itp.).
 */
export function buildConclusions(
  kpis: ReportKpis,
  trendPoints: TrendPoint[],
): string[] {
  const conclusions: string[] = [];

  if (kpis.complianceScore != null) {
    const score = Math.round(kpis.complianceScore);
    const ocena =
      score >= 80 ? "dobry" : score >= 50 ? "wymagający uwagi" : "niski";
    conclusions.push(
      `Zgodność oprogramowania z dokumentacją wynosi ${score}% — poziom ${ocena}.`,
    );
  }

  if (kpis.criticalCount > 0) {
    conclusions.push(
      `Wykryto ${kpis.criticalCount} problemów o znaczeniu krytycznym — zalecamy ich naprawę w pierwszej kolejności.`,
    );
  } else if (kpis.totalFindings > 0) {
    conclusions.push(
      "Nie wykryto problemów o znaczeniu krytycznym — pozostałe uwagi nie blokują dalszych prac.",
    );
  } else {
    conclusions.push(
      "Analiza nie wykazała problemów — oprogramowanie jest zgodne z dostarczoną dokumentacją.",
    );
  }

  if (kpis.totalFindings > 0) {
    conclusions.push(
      `Łącznie zidentyfikowano ${kpis.totalFindings} uwag: ` +
        `${kpis.criticalCount} krytycznych, ${kpis.highCount} ważnych, ` +
        `${kpis.mediumCount} umiarkowanych i ${kpis.lowCount} drobnych.`,
    );
  }

  if (kpis.testCasesTotal > 0) {
    conclusions.push(
      `Przygotowano ${kpis.testCasesTotal} przypadków testowych, z czego ` +
        `${kpis.testCasesReady} jest gotowych do uruchomienia, a ` +
        `${kpis.testCasesPassed} zakończyło się wynikiem pozytywnym.`,
    );
  }

  if (kpis.coveragePercentage != null) {
    conclusions.push(
      `Pokrycie wymagań biznesowych wynosi ${Math.round(kpis.coveragePercentage)}%.`,
    );
  }

  if (trendPoints.length >= 2) {
    const first = trendPoints[0].score;
    const last = trendPoints[trendPoints.length - 1].score;
    const diff = Math.round(last - first);
    if (diff > 0) {
      conclusions.push(
        `Jakość projektu poprawia się — wynik zgodności wzrósł o ${diff} punktów od pierwszej analizy.`,
      );
    } else if (diff < 0) {
      conclusions.push(
        `Wynik zgodności spadł o ${Math.abs(diff)} punktów od pierwszej analizy — zalecamy przegląd ostatnich zmian.`,
      );
    } else {
      conclusions.push(
        "Wynik zgodności utrzymuje się na stałym poziomie między analizami.",
      );
    }
  }

  return conclusions;
}

/**
 * Story 6.6 — generator raportów. Agreguje dane z istniejących endpointów
 * BE (security-findings, gap-findings, compliance, compliance/trend,
 * test-cases) i buduje raport po stronie FE; postęp generowania (AC7)
 * odzwierciedla realne etapy: pobieranie danych → trend → treść → render.
 */
@Injectable({ providedIn: "root" })
export class ReportService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;
  private readonly securityService = inject(SecurityScanService);
  private readonly gapService = inject(GapAnalysisService);
  private readonly testCaseService = inject(TestCaseService);

  readonly reportTypeSignal = signal<ReportType>("executive");
  readonly reportStatusSignal = signal<ReportStatus>("idle");
  readonly reportStageSignal = signal(0);
  readonly reportDataSignal = signal<ReportData | null>(null);

  generateReport(projectId: string, type: ReportType): Observable<ReportData> {
    this.reportTypeSignal.set(type);
    this.reportStatusSignal.set("generating");
    this.reportStageSignal.set(0);
    this.reportDataSignal.set(null);

    // Etap 1: Zbieranie danych (best-effort — brak pojedynczego źródła nie
    // przerywa generowania raportu).
    return forkJoin({
      security: this.securityService
        .listFindings(projectId, { page: 1, pageSize: 200 })
        .pipe(catchError(() => of(null))),
      gaps: this.gapService
        .getFindings(projectId, { page: 1, size: 100 })
        .pipe(catchError(() => of(null))),
      summary: this.gapService
        .getSummary(projectId)
        .pipe(catchError(() => of(null))),
      compliance: this.http
        .get<ComplianceScore>(`${this.apiUrl}/projects/${projectId}/compliance`)
        .pipe(catchError(() => of(null))),
      modules: this.http
        .get<
          ModuleScore[]
        >(`${this.apiUrl}/projects/${projectId}/compliance/modules`)
        .pipe(catchError(() => of([] as ModuleScore[]))),
      testCases: this.testCaseService
        .list({ projectId, page: 1, pageSize: 200 })
        .pipe(catchError(() => of(null))),
    }).pipe(
      // Etap 2: Analiza trendów.
      concatMap((collected) => {
        this.reportStageSignal.set(1);
        return this.gapService.getTrend(projectId, 20).pipe(
          catchError(() => of({ points: [] as TrendPoint[] })),
          map((trend) => ({ collected, trend })),
        );
      }),
      // Etap 3: Generowanie treści.
      concatMap(({ collected, trend }) => {
        this.reportStageSignal.set(2);
        return timer(250).pipe(
          map(() => this.composeReport(projectId, collected, trend.points)),
        );
      }),
      // Etap 4: Renderowanie.
      concatMap((data) => {
        this.reportStageSignal.set(3);
        return timer(250).pipe(map(() => data));
      }),
      tap({
        next: (data) => {
          this.reportDataSignal.set(data);
          this.reportStatusSignal.set("done");
        },
        error: () => this.reportStatusSignal.set("error"),
      }),
    );
  }

  reset(): void {
    this.reportStatusSignal.set("idle");
    this.reportStageSignal.set(0);
    this.reportDataSignal.set(null);
  }

  private composeReport(
    projectId: string,
    collected: {
      security: { findings: SecurityFinding[] } | null;
      gaps: { findings: GapFinding[] } | null;
      summary: GapAnalysisSummary | null;
      compliance: ComplianceScore | null;
      modules: ModuleScore[] | null;
      testCases: unknown;
    },
    trendPoints: TrendPoint[],
  ): ReportData {
    const findings: ReportFinding[] = [
      ...(collected.security?.findings ?? []).map(toReportFinding),
      ...(collected.gaps?.findings ?? []).map(gapToReportFinding),
    ].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);

    const severityCounts: Record<ResultSeverity, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    };
    for (const f of findings) severityCounts[f.severity] += 1;

    const statusCounts = this.testCaseService.statusCountsSignal();
    const kpis: ReportKpis = {
      complianceScore: collected.compliance?.score ?? null,
      coveragePercentage: collected.summary?.coveragePercentage ?? null,
      totalFindings: findings.length,
      criticalCount: severityCounts.critical,
      highCount: severityCounts.high,
      mediumCount: severityCounts.medium,
      lowCount: severityCounts.low,
      testCasesTotal: this.testCaseService.totalSignal(),
      testCasesReady: statusCounts.ready,
      testCasesPassed: statusCounts.passed,
    };

    return {
      projectId,
      generatedAt: new Date().toISOString(),
      kpis,
      severityCounts,
      moduleScores: (collected.modules ?? []).slice(0, 15),
      trendPoints,
      conclusions: buildConclusions(kpis, trendPoints),
      findings,
    };
  }
}
