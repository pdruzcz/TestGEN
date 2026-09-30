import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpParams } from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../../environments/environment";

/**
 * HTTP wrapper for Story 1.6 (uploads + git connect).
 *
 * All response payloads arrive after the global snakeCaseInterceptor has
 * transformed keys, so we declare camelCase interfaces on the client side.
 * Outgoing request bodies are likewise transformed — except FormData, which
 * is passed through untouched (see core/interceptors/snake-case.interceptor.ts).
 *
 * NOTE: HttpParams (query strings) are NOT touched by the interceptor — always
 * use the backend's parameter names directly there.
 */
export interface FileInfo {
  id: string | null;
  filename: string;
  fileSize: number;
  mimeType: string | null;
  sha256Hash: string | null;
  status: "accepted" | "rejected";
  rejectionReason: string | null;
}

export interface UploadResponse {
  projectId: string;
  acceptedFiles: FileInfo[];
  rejectedFiles: FileInfo[];
  totalAccepted: number;
  totalRejected: number;
}

export interface ConnectRepoPayload {
  repoUrl: string;
  branch: string;
  authToken?: string | null;
}

export interface ConnectRepoResponse {
  projectId: string;
  repoUrl: string;
  branch: string;
  filesIndexed: number;
  message: string;
}

export interface SourceFile {
  id: string;
  projectId: string;
  filename: string;
  fileSize: number;
  mimeType: string | null;
  sha256Hash: string;
  detectedLanguage: string | null;
  detectedFramework: string | null;
  isCleanedUp: boolean;
  createdAt: string | null;
}

export interface SourceFileListResponse {
  files: SourceFile[];
  total: number;
}

export interface AnalysisResponse {
  analysis: {
    rawResponse: string;
    model: string;
    usage: Record<string, unknown>;
  };
  fileId: string;
  projectId: string;
}

@Injectable({ providedIn: "root" })
export class ProjectFilesService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  uploadFiles(projectId: string, files: File[]): Observable<UploadResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file, file.name);
    }
    return this.http.post<UploadResponse>(
      `${this.apiUrl}/projects/${projectId}/upload`,
      formData,
    );
  }

  connectRepo(
    projectId: string,
    payload: ConnectRepoPayload,
  ): Observable<ConnectRepoResponse> {
    return this.http.post<ConnectRepoResponse>(
      `${this.apiUrl}/projects/${projectId}/connect-repo`,
      {
        repoUrl: payload.repoUrl,
        branch: payload.branch,
        authToken: payload.authToken ?? null,
      },
    );
  }

  listFiles(
    projectId: string,
    page = 1,
    pageSize = 20,
  ): Observable<SourceFileListResponse> {
    const params = new HttpParams()
      .set("page", String(page))
      .set("page_size", String(pageSize));
    return this.http.get<SourceFileListResponse>(
      `${this.apiUrl}/projects/${projectId}/files`,
      { params },
    );
  }

  analyzeFile(projectId: string, fileId: string): Observable<AnalysisResponse> {
    return this.http.post<AnalysisResponse>(
      `${this.apiUrl}/projects/${projectId}/files/${fileId}/analyze`,
      {},
    );
  }

  /** Soft-delete a source file — DELETE /projects/{id}/files/{fileId} (204).
   * Requires Owner/Admin role (backend enforces; 403 otherwise). */
  deleteFile(projectId: string, fileId: string): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/projects/${projectId}/files/${fileId}`,
    );
  }
}
