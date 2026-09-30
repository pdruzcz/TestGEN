import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../../environments/environment";

/**
 * HTTP wrapper for the security module (Epic 4). Responses pass through the
 * global snakeCaseInterceptor, so camelCase interfaces are declared client-side
 * while request bodies/params use snake_case.
 */

export type ScanType = "sast" | "taint" | "dependency" | "config" | "dast";
export type EngineMode = "native" | "llm" | "hybrid";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type FindingStatus =
  | "open"
  | "acknowledged"
  | "fixed"
  | "false_positive";

export interface SecurityScanRequest {
  scanType: ScanType;
  targetUrl?: string | null;
  authConfig?: Record<string, string> | null;
}

export interface SecurityScanResponse {
  scanId: string;
  taskId: string | null;
  status: string;
  createdAt: string | null;
}

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface SecurityScanStatus {
  scanId: string;
  scanType: ScanType;
  engineMode: EngineMode;
  status: string;
  findingsCount: number;
  severityCounts: SeverityCounts;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
}

export interface SecurityScanList {
  scans: SecurityScanStatus[];
  total: number;
}

export type TaintNodeType = "source" | "transform" | "sanitizer" | "sink";

export interface TaintPathNode {
  file: string | null;
  line: number;
  variable: string | null;
  operation: string;
  nodeType: TaintNodeType;
}

export interface TaintPath {
  source: string;
  sink: string;
  sinkType: string;
  taintType: string;
  variable: string | null;
  sanitizer: string | null;
  sanitizerAdequate: boolean;
  path: TaintPathNode[];
}

export interface SecurityFinding {
  id: string;
  scanId: string;
  scanType: ScanType;
  vulnerabilityType: string;
  severity: Severity;
  cweId: string | null;
  owaspCategory: string | null;
  filePath: string | null;
  lineStart: number | null;
  lineEnd: number | null;
  codeSnippet: string | null;
  description: string;
  confidence: number;
  source: string;
  status: FindingStatus;
  taintPath: TaintPath | null;
  findingMetadata: Record<string, unknown> | null;
  recommendation: string | null;
  cvssScore: number | null;
  cvssVector: string | null;
  priority: number | null;
  effort: string | null;
  escalationReason: string | null;
  createdAt: string | null;
}

export interface SecurityFindingList {
  findings: SecurityFinding[];
  total: number;
  page: number;
  pageSize: number;
}

export interface SecurityReportSummary {
  totalFindings: number;
  severityCounts: Record<string, number>;
  sourceCounts: Record<string, number>;
}

export interface SecurityReport {
  summary: SecurityReportSummary;
  findings: SecurityFinding[];
  dedupCount: number;
  correlationCount: number;
}

export interface RepairStep {
  findingId: string;
  vulnerabilityType: string;
  severity: Severity;
  cvssScore: number | null;
  effort: string | null;
  priority: number | null;
}

export interface SecurityDashboard {
  cvssDistribution: Record<string, number>;
  top10Findings: SecurityFinding[];
  repairSequence: RepairStep[];
  totalFindings: number;
}

export type RecommendationEngineMode = "native" | "llm";

export interface Recommendation {
  findingId: string;
  problemDescription: string;
  riskDescription: string;
  fixDescription: string;
  fixedCodeSnippet: string;
  diff: string;
  language: string;
  engineSource: string;
}

export interface ProofOfConcept {
  findingId: string;
  payload: string;
  reproductionSteps: string[];
  expectedEffect: string;
  severity: string;
  isSafe: boolean;
  disclaimer: string;
  engineSource: string;
}

export type ConflictSeverity = "critical" | "warning";

export interface ConflictReport {
  patchAId: string;
  patchBId: string;
  overlappingLines: number[];
  severity: ConflictSeverity;
}

export interface PatchResult {
  findingId: string;
  filePath: string;
  patchContent: string;
  patchFilename: string;
  isValid: boolean;
  conflicts: ConflictReport[];
}

export interface PatchPreview {
  findingId: string;
  filePath: string;
  patchContent: string;
  originalCode: string;
  fixedCode: string;
  isValid: boolean;
}

export interface BatchPatchResult {
  patches: PatchResult[];
  conflicts: ConflictReport[];
  total: number;
}

export type SbomFormat = "cyclonedx" | "spdx";

export type ConfigType = "docker" | "kubernetes" | "terraform" | "config";

@Injectable({ providedIn: "root" })
export class SecurityScanService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Launch a scan. Returns 202 + scan id + task id. */
  startScan(
    projectId: string,
    request: SecurityScanRequest,
  ): Observable<SecurityScanResponse> {
    return this.http.post<SecurityScanResponse>(
      `${this.apiUrl}/projects/${projectId}/security-scan`,
      {
        scan_type: request.scanType,
        target_url: request.targetUrl ?? null,
        auth_config: request.authConfig ?? null,
      },
    );
  }

  /** List the project's scans (most recent first). */
  listScans(projectId: string): Observable<SecurityScanList> {
    return this.http.get<SecurityScanList>(
      `${this.apiUrl}/projects/${projectId}/security-scans`,
    );
  }

  /** Poll a single scan's status + severity breakdown. */
  getScan(projectId: string, scanId: string): Observable<SecurityScanStatus> {
    return this.http.get<SecurityScanStatus>(
      `${this.apiUrl}/projects/${projectId}/security-scans/${scanId}`,
    );
  }

  /** List findings with optional filters. */
  listFindings(
    projectId: string,
    options: {
      scanId?: string;
      severity?: Severity;
      scanType?: ScanType;
      status?: FindingStatus;
      vulnerabilityType?: string;
      filePath?: string;
      cweId?: string;
      page?: number;
      pageSize?: number;
    } = {},
  ): Observable<SecurityFindingList> {
    let params = new HttpParams()
      .set("page", String(options.page ?? 1))
      .set("page_size", String(options.pageSize ?? 50));
    if (options.scanId) params = params.set("scan_id", options.scanId);
    if (options.severity) params = params.set("severity", options.severity);
    if (options.scanType) params = params.set("scan_type", options.scanType);
    if (options.status) params = params.set("status", options.status);
    if (options.vulnerabilityType)
      params = params.set("vulnerability_type", options.vulnerabilityType);
    if (options.filePath) params = params.set("file_path", options.filePath);
    if (options.cweId) params = params.set("cwe_id", options.cweId);
    return this.http.get<SecurityFindingList>(
      `${this.apiUrl}/projects/${projectId}/security-findings`,
      { params },
    );
  }

  /** Fetch the aggregated, deduplicated, correlated security report (Story 4.7). */
  getReport(projectId: string): Observable<SecurityReport> {
    return this.http.get<SecurityReport>(
      `${this.apiUrl}/projects/${projectId}/security-report`,
    );
  }

  /** Fetch the risk dashboard: CVSS distribution, top 10 and repair sequence (Story 4.8). */
  getDashboard(projectId: string): Observable<SecurityDashboard> {
    return this.http.get<SecurityDashboard>(
      `${this.apiUrl}/projects/${projectId}/security-dashboard`,
    );
  }

  /** Change a finding's triage status (acknowledge / false_positive / fixed). */
  updateFindingStatus(
    projectId: string,
    findingId: string,
    status: FindingStatus,
  ): Observable<SecurityFinding> {
    return this.http.patch<SecurityFinding>(
      `${this.apiUrl}/projects/${projectId}/security-findings/${findingId}/status`,
      { status },
    );
  }

  /** Generate a remediation recommendation (problem/risk/fix/diff) for a finding (Story 4.9). */
  generateRecommendation(
    projectId: string,
    findingId: string,
  ): Observable<Recommendation> {
    return this.http.post<Recommendation>(
      `${this.apiUrl}/projects/${projectId}/security-findings/${findingId}/recommendation`,
      {},
    );
  }

  /** Generate a safe proof-of-concept for an injection finding (Story 4.10). */
  generatePoc(
    projectId: string,
    findingId: string,
  ): Observable<ProofOfConcept> {
    return this.http.post<ProofOfConcept>(
      `${this.apiUrl}/projects/${projectId}/security-findings/${findingId}/generate-poc`,
      {},
    );
  }

  /** Fetch a previously generated PoC for a finding (Story 4.10). */
  getPoc(projectId: string, findingId: string): Observable<ProofOfConcept> {
    return this.http.get<ProofOfConcept>(
      `${this.apiUrl}/projects/${projectId}/security-findings/${findingId}/poc`,
    );
  }

  /** Generate a git-apply-ready patch for a finding and persist it (Story 4.11). */
  generatePatch(projectId: string, findingId: string): Observable<PatchResult> {
    return this.http.post<PatchResult>(
      `${this.apiUrl}/projects/${projectId}/security-findings/${findingId}/generate-patch`,
      {},
    );
  }

  /** Fetch a previously generated patch for a finding (Story 4.11). */
  getPatch(projectId: string, findingId: string): Observable<PatchResult> {
    return this.http.get<PatchResult>(
      `${this.apiUrl}/projects/${projectId}/security-findings/${findingId}/patch`,
    );
  }

  /** Preview before/after code and the diff without persisting (Story 4.11). */
  previewPatch(projectId: string, findingId: string): Observable<PatchPreview> {
    return this.http.get<PatchPreview>(
      `${this.apiUrl}/projects/${projectId}/security-findings/${findingId}/patch/preview`,
    );
  }

  /** Download the stored .patch file as text for a finding (Story 4.11). */
  downloadPatch(projectId: string, findingId: string): Observable<Blob> {
    return this.http.get(
      `${this.apiUrl}/projects/${projectId}/security-findings/${findingId}/patch/download`,
      {
        responseType: "blob",
      },
    );
  }

  /** Generate one patch per finding and report same-file conflicts (Story 4.11). */
  generateBatchPatches(
    projectId: string,
    findingIds: string[] = [],
  ): Observable<BatchPatchResult> {
    return this.http.post<BatchPatchResult>(
      `${this.apiUrl}/projects/${projectId}/security-patches/batch`,
      {
        finding_ids: findingIds,
      },
    );
  }

  /** List potential merge conflicts between findings in the same file (Story 4.11). */
  listPatchConflicts(projectId: string): Observable<ConflictReport[]> {
    return this.http.get<ConflictReport[]>(
      `${this.apiUrl}/projects/${projectId}/security-patches/conflicts`,
    );
  }

  /** Download the generated SBOM (CycloneDX or SPDX) for a dependency scan. */
  getSbom(
    projectId: string,
    scanId: string,
    sbomFormat: SbomFormat = "cyclonedx",
  ): Observable<Record<string, unknown>> {
    const params = new HttpParams().set("sbom_format", sbomFormat);
    return this.http.get<Record<string, unknown>>(
      `${this.apiUrl}/projects/${projectId}/security-scans/${scanId}/sbom`,
      { params },
    );
  }
}
