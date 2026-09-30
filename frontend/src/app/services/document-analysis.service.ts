import { inject, Injectable } from "@angular/core";
import { HttpClient, HttpParams, HttpResponse } from "@angular/common/http";
import { Observable, BehaviorSubject, switchMap, tap, of, map } from "rxjs";
import { catchError, shareReplay } from "rxjs/operators";

// Interfaces matching backend API responses
export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  file_size: number;
  content_type: string;
  uploaded_at: string;
  status: string;
  project_id: string;
}

export interface AnalysisStatusResponse {
  document_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  available_results: string[];
  error?: string;
}

/**
 * Complete analysis results (GET /documents/{id}/analysis).
 *
 * Field names are camelCase: the global ``snakeCaseInterceptor`` converts the
 * snake_case API response (``gap_analysis`` → ``gapAnalysis``, …) automatically.
 */
export interface AnalysisResult {
  documentId: string;
  filename: string;
  mode: string;
  classification: any;
  requirements: Requirement[];
  glossary: any;
  inconsistencies: Inconsistency[];
  gapAnalysis: any;
  traceability: any;
  testGeneration: any;
}

/**
 * Persisted requirement (Story 2.4/2.5).
 *
 * Field names are camelCase: the global ``snakeCaseInterceptor`` converts the
 * snake_case API response (``req_id`` → ``reqId``, …) automatically.
 */
export interface Requirement {
  documentId?: string;
  documentFilename?: string | null;
  reqId: string;
  type: "functional" | "non-functional";
  priority?: string | null;
  text: string;
  sourceSectionId?: string;
  sourceSectionTitle?: string | null;
  confidence: number;
  extractionMethod?: string;
  status?: string;
  /** Extraction origin (Story 2.5): "native" | "llm". */
  source?: string;
  /** Optional LLM justification (Story 2.5). */
  reasoning?: string | null;
}

/** Mutation body for PUT /documents/{id}/requirements/{reqId} (Story 2.4). */
export interface RequirementUpdate {
  status?: string;
  text?: string;
  priority?: string;
}

/**
 * A code-entity mapping for a glossary term (Story 2.6, AC2).
 * camelCase — klucze konwertuje globalny ``snakeCaseInterceptor``.
 */
export interface CodeMapping {
  name: string;
  type: string; // function | method | class | module
  similarity: number;
  isConfirmed: boolean;
}

/**
 * A persisted glossary term with code mappings (Story 2.6).
 * camelCase — klucze konwertuje globalny ``snakeCaseInterceptor``.
 */
export interface GlossaryTerm {
  documentId: string;
  documentFilename?: string | null;
  term: string;
  definition: string | null;
  occurrencesCount: number;
  termType: "domain" | "technical" | "business" | "acronym";
  sourceSections: { sectionId: string; title: string }[];
  isVerified: boolean;
  codeMappings: CodeMapping[];
}

export interface GlossaryList {
  documentId: string;
  filename: string;
  total: number;
  terms: GlossaryTerm[];
}

/** Mutation body for PUT /documents/{id}/glossary/{term} (Story 2.6). */
export interface GlossaryTermUpdate {
  definition?: string;
  termType?: GlossaryTerm["termType"];
  isVerified?: boolean;
  confirmedMappingIds?: string[];
}

export type InconsistencyType =
  | "contradiction"
  | "terminology"
  | "missing_reference"
  | "duplicate";
export type InconsistencySeverity = "critical" | "high" | "medium" | "low";
export type InconsistencyStatus =
  | "open"
  | "accepted"
  | "false_positive"
  | "fixed";

/**
 * A persisted inconsistency (Story 2.7).
 * camelCase — klucze konwertuje globalny ``snakeCaseInterceptor``.
 */
export interface Inconsistency {
  documentId?: string;
  documentFilename?: string | null;
  inconsistencyId: string;
  type: InconsistencyType;
  severity: InconsistencySeverity;
  description: string;
  affectedRequirements: string[];
  suggestion?: string | null;
  sourceSectionId?: string | null;
  status: InconsistencyStatus;
}

export interface InconsistencyList {
  documentId: string;
  filename: string;
  total: number;
  inconsistencies: Inconsistency[];
}

/**
 * A traceability matrix row (Story 2.9).
 * camelCase — klucze konwertuje globalny ``snakeCaseInterceptor``.
 */
export interface TraceabilityEntry {
  requirementId: string;
  requirementText: string;
  codeEntities: string[];
  testCases: string[];
  coverageStatus: "full" | "partial" | "none";
  sourceSectionId: string;
}

export interface TraceabilityMatrix {
  documentName: string;
  totalRequirements: number;
  fullCoverage: number;
  partialCoverage: number;
  noCoverage: number;
  coveragePercentage: number;
  entries: TraceabilityEntry[];
}

@Injectable({ providedIn: "root" })
export class DocumentAnalysisService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = "/api/v1";

  // Cache for document status
  private statusCache = new Map<
    string,
    BehaviorSubject<AnalysisStatusResponse>
  >();

  /**
   * Upload a document for analysis
   */
  uploadDocument(
    projectId: string,
    file: File,
  ): Observable<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);

    return this.http.post<DocumentUploadResponse>(
      `${this.apiUrl}/documents/upload/${projectId}`,
      formData,
    );
  }

  /**
   * Get analysis status for a document
   */
  getAnalysisStatus(documentId: string): Observable<AnalysisStatusResponse> {
    // Check cache first
    if (!this.statusCache.has(documentId)) {
      this.statusCache.set(
        documentId,
        new BehaviorSubject<AnalysisStatusResponse>({
          document_id: documentId,
          status: "pending",
          progress: 0,
          available_results: [],
        }),
      );
    }

    return this.http
      .get<AnalysisStatusResponse>(
        `${this.apiUrl}/documents/${documentId}/status`,
      )
      .pipe(
        tap((status) => this.statusCache.get(documentId)?.next(status)),
        shareReplay(1),
      );
  }

  /**
   * Poll analysis status until completion or timeout
   */
  pollAnalysisStatus(
    documentId: string,
    intervalMs: number = 2000,
    maxAttempts: number = 30,
  ): Observable<AnalysisStatusResponse> {
    let attempts = 0;

    return new Observable<AnalysisStatusResponse>((observer) => {
      const poll = () => {
        this.getAnalysisStatus(documentId).subscribe({
          next: (status) => {
            observer.next(status);

            if (status.status === "completed" || status.status === "failed") {
              observer.complete();
              return;
            }

            attempts++;
            if (attempts >= maxAttempts) {
              observer.complete();
              return;
            }

            setTimeout(poll, intervalMs);
          },
          error: (err) => observer.error(err),
        });
      };

      poll();
    });
  }

  /**
   * Get complete analysis results
   */
  getAnalysisResults(documentId: string): Observable<AnalysisResult> {
    return this.http.get<AnalysisResult>(
      `${this.apiUrl}/documents/${documentId}/analysis`,
    );
  }

  /**
   * Get requirements only
   */
  getRequirements(documentId: string): Observable<{
    documentId: string;
    filename: string;
    mode: string;
    total: number;
    requirements: Requirement[];
  }> {
    return this.http.get<{
      documentId: string;
      filename: string;
      mode: string;
      total: number;
      requirements: Requirement[];
    }>(`${this.apiUrl}/documents/${documentId}/requirements`);
  }

  /**
   * Accept a requirement — POST /documents/{id}/requirements/{reqId}/accept (Story 2.4)
   */
  acceptRequirement(
    documentId: string,
    reqId: string,
  ): Observable<Requirement> {
    return this.http.post<Requirement>(
      `${this.apiUrl}/documents/${documentId}/requirements/${reqId}/accept`,
      {},
    );
  }

  /**
   * Reject a requirement — POST /documents/{id}/requirements/{reqId}/reject (Story 2.4)
   */
  rejectRequirement(
    documentId: string,
    reqId: string,
  ): Observable<Requirement> {
    return this.http.post<Requirement>(
      `${this.apiUrl}/documents/${documentId}/requirements/${reqId}/reject`,
      {},
    );
  }

  /**
   * Update (edit/undo) a requirement — PUT /documents/{id}/requirements/{reqId} (Story 2.4)
   */
  updateRequirement(
    documentId: string,
    reqId: string,
    body: RequirementUpdate,
  ): Observable<Requirement> {
    return this.http.put<Requirement>(
      `${this.apiUrl}/documents/${documentId}/requirements/${reqId}`,
      body,
    );
  }

  /**
   * Wymagania ze wszystkich dokumentów projektu (widok nawigacji projektu).
   */
  getProjectRequirements(projectId: string): Observable<{
    projectId: string;
    total: number;
    documents: number;
    requirements: Requirement[];
  }> {
    return this.http.get<{
      projectId: string;
      total: number;
      documents: number;
      requirements: Requirement[];
    }>(`${this.apiUrl}/projects/${projectId}/requirements`);
  }

  /**
   * Glosariusz ze wszystkich dokumentów projektu (z dokumentem źródłowym).
   */
  getProjectGlossary(projectId: string): Observable<
    GlossaryList & {
      projectId: string;
      documents: number;
    }
  > {
    return this.http
      .get<
        GlossaryList & { projectId: string; documents: number }
      >(`${this.apiUrl}/projects/${projectId}/glossary`)
      .pipe(
        map((res) => ({
          ...this.normalizeGlossary(res),
          projectId: res.projectId,
          documents: res.documents,
        })),
      );
  }

  /**
   * Niespójności ze wszystkich dokumentów projektu (z dokumentem źródłowym).
   */
  getProjectInconsistencies(projectId: string): Observable<
    InconsistencyList & {
      projectId: string;
      documents: number;
    }
  > {
    return this.http.get<
      InconsistencyList & { projectId: string; documents: number }
    >(`${this.apiUrl}/projects/${projectId}/inconsistencies`);
  }

  /**
   * Get persisted glossary terms — GET /documents/{id}/glossary (Story 2.6).
   */
  getGlossary(documentId: string): Observable<GlossaryList> {
    return this.http
      .get<GlossaryList>(`${this.apiUrl}/documents/${documentId}/glossary`)
      .pipe(map((res) => this.normalizeGlossary(res)));
  }

  /**
   * Normalizacja defensywna listy terminów: tablice z BE (codeMappings,
   * sourceSections) mogą być nieobecne w starszych zapisach result_data —
   * bez tego szablon rzuca TypeError na ``.length`` i ucina renderowanie.
   */
  private normalizeGlossary(res: GlossaryList): GlossaryList {
    return {
      ...res,
      terms: (res.terms ?? []).map((t) => ({
        ...t,
        codeMappings: t.codeMappings ?? [],
        sourceSections: t.sourceSections ?? [],
      })),
    };
  }

  /**
   * Edit a glossary term — PUT /documents/{id}/glossary/{term} (Story 2.6).
   */
  updateGlossaryTerm(
    documentId: string,
    term: string,
    body: GlossaryTermUpdate,
  ): Observable<GlossaryTerm> {
    return this.http.put<GlossaryTerm>(
      `${this.apiUrl}/documents/${documentId}/glossary/${encodeURIComponent(term)}`,
      body,
    );
  }

  /**
   * Rebuild code mappings — POST /documents/{id}/glossary/map-to-code (Story 2.6).
   */
  mapGlossaryToCode(documentId: string): Observable<GlossaryList> {
    return this.http
      .post<GlossaryList>(
        `${this.apiUrl}/documents/${documentId}/glossary/map-to-code`,
        {},
      )
      .pipe(map((res) => this.normalizeGlossary(res)));
  }

  /**
   * Get persisted inconsistencies — GET /documents/{id}/inconsistencies (Story 2.7).
   */
  getInconsistencies(documentId: string): Observable<InconsistencyList> {
    return this.http
      .get<InconsistencyList>(
        `${this.apiUrl}/documents/${documentId}/inconsistencies`,
      )
      .pipe(
        // Normalizacja defensywna: starsze zapisy result_data (i stare bundle
        // BE) mogą nie zawierać tablicy — bez tego szablon rzuca TypeError
        // na `.length` i przerywa renderowanie listy w połowie.
        map((res) => ({
          ...res,
          inconsistencies: (res.inconsistencies ?? []).map((inc) => ({
            ...inc,
            affectedRequirements: inc.affectedRequirements ?? [],
          })),
        })),
      );
  }

  /**
   * Update an inconsistency's workflow status —
   * PUT /documents/{id}/inconsistencies/{inconsistencyId} (Story 2.7, AC4).
   */
  updateInconsistencyStatus(
    documentId: string,
    inconsistencyId: string,
    status: InconsistencyStatus,
  ): Observable<Inconsistency> {
    return this.http.put<Inconsistency>(
      `${this.apiUrl}/documents/${documentId}/inconsistencies/${encodeURIComponent(inconsistencyId)}`,
      { status },
    );
  }

  /**
   * Compare native vs LLM analysis
   */
  compareAnalysisModes(
    documentId: string,
    modeA: string = "native",
    modeB: string = "llm",
  ): Observable<any> {
    return this.http.post<any>(
      `${this.apiUrl}/documents/${documentId}/compare`,
      { mode_a: modeA, mode_b: modeB },
    );
  }

  /**
   * Get cached status for immediate access
   */
  getCachedStatus(documentId: string): AnalysisStatusResponse | null {
    const subject = this.statusCache.get(documentId);
    return subject ? subject.value : null;
  }

  /**
   * Clear cached status
   */
  clearStatusCache(documentId?: string): void {
    if (documentId) {
      this.statusCache.delete(documentId);
    } else {
      this.statusCache.clear();
    }
  }
}
