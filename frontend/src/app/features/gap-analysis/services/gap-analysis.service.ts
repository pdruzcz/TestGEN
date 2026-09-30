import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../environments/environment";

export type GapType = "missing" | "different" | "extra" | "inconsistent";
export type GapSeverity = "critical" | "warning" | "info";
export type EngineMode = "native" | "llm" | "hybrid";

export interface GapAnalysisRequest {
  documentIds?: string[];
  engineMode?: EngineMode;
}

export interface GapAnalysisTriggerResponse {
  taskId: string;
  status: string;
}

export interface GapFinding {
  id: string;
  projectId: string;
  requirementId: string | null;
  codeEntityId: string | null;
  gapType: string;
  description: string;
  requirementText: string | null;
  codeReference: string | null;
  matchScore: number;
  matchMethod: string | null;
  context: Record<string, unknown> | null;
  severity: string;
  skeletonCode: string | null;
  skeletonLanguage: string | null;
  createdAt: string;
}

export interface GapAnalysisSummary {
  totalRequirements: number;
  totalCodeEntities: number;
  missingCount: number;
  differentCount: number;
  extraCount: number;
  inconsistentCount: number;
  avgMatchScore: number;
  coveragePercentage: number;
}

export interface GapFindingsListResponse {
  findings: GapFinding[];
  total: number;
  page: number;
  size: number;
  summary: GapAnalysisSummary;
}

@Injectable({ providedIn: "root" })
export class GapAnalysisService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  startAnalysis(
    projectId: string,
    request: GapAnalysisRequest,
  ): Observable<GapAnalysisTriggerResponse> {
    return this.http.post<GapAnalysisTriggerResponse>(
      `${this.apiUrl}/projects/${projectId}/gap-analysis`,
      {
        document_ids: request.documentIds ?? [],
        engine_mode: request.engineMode ?? "native",
      },
    );
  }

  getFindings(
    projectId: string,
    options?: {
      gapType?: string;
      minScore?: number;
      severity?: string;
      matchMethod?: string;
      page?: number;
      size?: number;
    },
  ): Observable<GapFindingsListResponse> {
    let params = new HttpParams();
    if (options?.gapType) params = params.set("gap_type", options.gapType);
    if (options?.minScore !== undefined)
      params = params.set("min_score", options.minScore);
    if (options?.severity) params = params.set("severity", options.severity);
    if (options?.matchMethod)
      params = params.set("match_method", options.matchMethod);
    if (options?.page) params = params.set("page", options.page);
    if (options?.size) params = params.set("size", options.size);

    return this.http.get<GapFindingsListResponse>(
      `${this.apiUrl}/projects/${projectId}/gap-findings`,
      { params },
    );
  }

  getSummary(projectId: string): Observable<GapAnalysisSummary> {
    return this.http.get<GapAnalysisSummary>(
      `${this.apiUrl}/projects/${projectId}/gap-analysis/summary`,
    );
  }

  getFindingsByType(projectId: string): Observable<GapFindingsByTypeResponse> {
    return this.http.get<GapFindingsByTypeResponse>(
      `${this.apiUrl}/projects/${projectId}/gap-findings/by-type`,
    );
  }

  generateSkeleton(
    projectId: string,
    findingId: string,
    language: string = "python",
  ): Observable<SkeletonResponse> {
    return this.http.post<SkeletonResponse>(
      `${this.apiUrl}/projects/${projectId}/gap-findings/${findingId}/skeleton`,
      { language },
    );
  }

  getSkeleton(
    projectId: string,
    findingId: string,
  ): Observable<SkeletonResponse> {
    return this.http.get<SkeletonResponse>(
      `${this.apiUrl}/projects/${projectId}/gap-findings/${findingId}/skeleton`,
    );
  }

  // ── Version comparison (Story 5.7) ────────────────────────────────────────

  createSnapshot(
    projectId: string,
    label?: string,
    notes?: string,
  ): Observable<ComplianceSnapshot> {
    return this.http.post<ComplianceSnapshot>(
      `${this.apiUrl}/projects/${projectId}/compliance/snapshot`,
      { label, notes },
    );
  }

  getSnapshots(projectId: string): Observable<ComplianceSnapshot[]> {
    return this.http.get<ComplianceSnapshot[]>(
      `${this.apiUrl}/projects/${projectId}/compliance/snapshots`,
    );
  }

  compareVersions(
    projectId: string,
    v1: string,
    v2: string,
  ): Observable<ComparisonResponse> {
    const params = new HttpParams().set("v1", v1).set("v2", v2);
    return this.http.get<ComparisonResponse>(
      `${this.apiUrl}/projects/${projectId}/compliance/compare`,
      { params },
    );
  }

  getTrend(projectId: string, limit: number = 20): Observable<TrendResponse> {
    const params = new HttpParams().set("limit", limit);
    return this.http.get<TrendResponse>(
      `${this.apiUrl}/projects/${projectId}/compliance/trend`,
      { params },
    );
  }
}

export interface GapTypeGroup {
  count: number;
  percentage: number;
  findings: GapFinding[];
}

export interface GapFindingsByTypeResponse {
  total: number;
  grouped: Record<string, GapTypeGroup>;
}

export interface SkeletonResponse {
  findingId: string;
  skeletonCode: string;
  language: string;
  functionName: string;
  error: string | null;
}

// ── Version comparison (Story 5.7) ──────────────────────────────────────────

export interface ComplianceSnapshot {
  id: string;
  projectId: string;
  analysisId: string | null;
  score: number;
  totalFindings: number;
  missingCount: number;
  differentCount: number;
  extraCount: number;
  inconsistentCount: number;
  avgMatchScore: number;
  coveragePercentage: number;
  label: string | null;
  notes: string | null;
  createdAt: string;
}

export interface SnapshotDiff {
  v1Score: number;
  v2Score: number;
  scoreDelta: number;
  direction: string;
  v1Total: number;
  v2Total: number;
  totalDelta: number;
  missingDelta: number;
  differentDelta: number;
  extraDelta: number;
  inconsistentDelta: number;
  coverageDelta: number;
  avgMatchScoreDelta: number;
}

export interface FindingDiff {
  key: string;
  status: string;
  gapType: string;
  v1Severity: string | null;
  v2Severity: string | null;
  v1Score: number | null;
  v2Score: number | null;
  requirementText: string | null;
}

export interface ComparisonResponse {
  v1Snapshot: ComplianceSnapshot;
  v2Snapshot: ComplianceSnapshot;
  snapshotDiff: SnapshotDiff;
  findingDiffs: FindingDiff[];
  summary: Record<string, number>;
}

export interface TrendPoint {
  snapshotId: string;
  timestamp: string | null;
  score: number;
  totalFindings: number;
  missing: number;
  different: number;
  extra: number;
  inconsistent: number;
  coverage: number;
  label: string | null;
}

export interface TrendResponse {
  points: TrendPoint[];
}
