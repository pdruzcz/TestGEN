import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams, HttpEventType } from "@angular/common/http";
import { Observable, filter, map, forkJoin, of, throwError } from "rxjs";
import { catchError } from "rxjs/operators";
import { environment } from "../../../../environments/environment";
import {
  DocSection,
  DocSectionsResponse,
} from "../../analysis/doc-sections/doc-sections.service";

/**
 * HTTP wrapper for Epic 2 (documentation upload and parsing).
 *
 * Handles document upload, list, and parsing status operations.
 * All response payloads arrive after the global snakeCaseInterceptor has
 * transformed keys, so we declare camelCase interfaces on the client side.
 */

export interface DocumentFile {
  id: string;
  projectId: string;
  filename: string;
  fileSize: number;
  fileCategory: "code" | "documentation" | "uml" | "gui";
  docFormat: "pdf" | "docx" | "md" | "html" | "txt" | null;
  pageCount: number | null;
  createdAt: string;
  isCleanedUp: boolean;
  processingStatus: "uploaded" | "processing" | "ready" | "failed";
  errorMessage: string | null;
  /** Document type from classification (Story 2.3). */
  docType?: string | null;
  /** Classification confidence 0-100 (Story 2.3). */
  classificationConfidence?: number | null;
  /** Classification reasoning/justification (Story 2.3). */
  classificationJustification?: string | null;
}

export interface DocumentUploadResponse {
  taskId: string;
  status: string;
  statusUrl: string;
  message: string;
}

export interface TaskStatusResponse {
  taskId: string;
  status: "pending" | "started" | "running" | "completed" | "failed";
  result: unknown;
  error: string | null;
}

export interface ParsedDocument {
  filename: string;
  format: string;
  rawText: string;
  sections: DocumentSection[];
  tables: TableData[];
  metadata: Record<string, unknown>;
}

export interface DocumentSection {
  sectionId: string;
  title: string;
  level: number;
  content: string;
  parentSectionId: string | null;
  pageNumber: number | null;
}

export interface TableData {
  tableId: string;
  headers: string[];
  rows: string[][];
  sourceSectionId: string;
}

export interface DocumentDetailResponse {
  sourceFile: DocumentFile;
  parsedDocument: ParsedDocument | null;
  analysisResult: unknown;
}

@Injectable({ providedIn: "root" })
export class DocumentService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /**
   * Upload documentation files to a project.
   * Returns 202 with task_id for async parsing.
   */
  uploadDocuments(
    projectId: string,
    files: File[],
    onProgress?: (progress: number) => void,
  ): Observable<DocumentUploadResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file, file.name);
    }

    return this.http
      .post<DocumentUploadResponse>(
        `${this.apiUrl}/projects/${projectId}/upload-documents`,
        formData,
        {
          reportProgress: true,
          observe: "events",
        },
      )
      .pipe(
        // Side-effect: report upload progress via callback
        map((event) => {
          if (event.type === HttpEventType.UploadProgress && onProgress) {
            const progress = event.total
              ? Math.round((event.loaded / event.total) * 100)
              : 0;
            onProgress(progress);
          }
          return event;
        }),
        // Only emit once the actual HTTP response arrives
        filter((event) => event.type === HttpEventType.Response),
        map(
          (event) =>
            event.body ?? {
              taskId: "",
              status: "unknown",
              statusUrl: "",
              message: "",
            },
        ),
      ) as Observable<DocumentUploadResponse>;
  }

  /**
   * List all documentation files for a project.
   */
  listDocuments(
    projectId: string,
    page = 1,
    pageSize = 20,
  ): Observable<{ documents: DocumentFile[]; total: number }> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));

    return this.http
      .get<
        DocumentFile[]
      >(`${this.apiUrl}/projects/${projectId}/documents`, { params, observe: "response" })
      .pipe(
        map((response) => {
          const documents = response.body ?? [];
          const total = Number(
            response.headers.get("X-Total-Count") ?? documents.length,
          );
          return { documents, total };
        }),
      );
  }

  /**
   * Get task status from Celery.
   */
  getTaskStatus(taskId: string): Observable<TaskStatusResponse> {
    return this.http.get<TaskStatusResponse>(`${this.apiUrl}/tasks/${taskId}`);
  }

  /**
   * Get detailed document info including parsed content.
   *
   * Source file metadata comes from the project files endpoint; the parsed
   * sections come from GET /documents/{id}/sections (Story 2.2). The sections
   * endpoint answers 202 while preprocessing is still running (and 404 when
   * the document does not exist) — both mean "not parsed yet" and yield
   * ``parsedDocument: null`` instead of an error banner.
   */
  getDocumentDetail(
    projectId: string,
    documentId: string,
  ): Observable<{
    sourceFile: DocumentFile;
    parsedDocument: ParsedDocument | null;
    analysisResult: unknown;
  }> {
    return forkJoin({
      sourceFile: this.http.get<DocumentFile>(
        `${this.apiUrl}/projects/${projectId}/documents/${documentId}`,
      ),
      sections: this.http
        .get<DocSectionsResponse>(
          `${this.apiUrl}/documents/${documentId}/sections`,
        )
        .pipe(
          catchError((err: { status?: number }) =>
            err.status === 404 ? of(null) : throwError(() => err),
          ),
          // 202 „preprocessing w toku" zwraca {detail: …} bez tablicy sekcji.
          map((res) => (res && Array.isArray(res.sections) ? res : null)),
        ),
    }).pipe(
      map(({ sourceFile, sections }) => ({
        sourceFile,
        parsedDocument: sections
          ? this.buildParsedDocument(sourceFile, sections)
          : null,
        analysisResult: null,
      })),
    );
  }

  /**
   * Build the flat ParsedDocument view-model from the reconstructed section
   * tree (depth-first; children follow their parent in reading order).
   */
  private buildParsedDocument(
    sourceFile: DocumentFile,
    sections: DocSectionsResponse,
  ): ParsedDocument {
    return {
      filename: sections.filename,
      format: sourceFile.docFormat ?? "",
      // Backend nie wystawia surowego tekstu — karta „Surowy tekst" jest
      // ukrywana, gdy rawText jest pusty (document-view).
      rawText: "",
      sections: this.flattenSections(sections.sections),
      // Endpoint sekcji nie zwraca tabel — karta „Tabele" pojawia się tylko
      // przy niepustej liście (document-view).
      tables: [],
      metadata: {},
    };
  }

  private flattenSections(
    nodes: DocSection[],
    parentSectionId: string | null = null,
  ): DocumentSection[] {
    const result: DocumentSection[] = [];
    for (const node of nodes) {
      result.push({
        sectionId: node.sectionId,
        title: node.title,
        level: node.level,
        content: node.content,
        parentSectionId: node.parentSectionId ?? parentSectionId,
        pageNumber: node.pageNumber,
      });
      if (node.children?.length) {
        result.push(...this.flattenSections(node.children, node.sectionId));
      }
    }
    return result;
  }

  /**
   * Re-run document parsing (re-extract sections/requirements/glossary).
   * Dispatches the backend ``parse_document_task`` — no quota consumed.
   */
  reanalyzeDocument(
    documentId: string,
  ): Observable<{ task_id: string; status: string; status_url: string }> {
    return this.http.post<{
      task_id: string;
      status: string;
      status_url: string;
    }>(`${this.apiUrl}/documents/${documentId}/reparse`, {});
  }

  /**
   * Re-classify a document by the global engine_mode (Story 2.3).
   * No body — the engine mode comes from backend Settings only.
   */
  classifyDocument(documentId: string): Observable<unknown> {
    return this.http.post(
      `${this.apiUrl}/documents/${documentId}/classify`,
      {},
    );
  }

  /**
   * Soft-delete a source file (mark as cleaned up, remove from MinIO).
   * Requires Owner or Admin role.
   */
  deleteDocument(projectId: string, documentId: string): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/projects/${projectId}/files/${documentId}`,
    );
  }
}
