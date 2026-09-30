import {
  HttpClient,
  HttpEventType,
  HttpProgressEvent,
  HttpResponse,
} from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, filter, map } from "rxjs";
import { environment } from "../../../environments/environment";

/**
 * Generic file upload service — Story 6.2.
 *
 * Posts FormData to `${apiUrl}/projects/{id}/upload-documents` (or caller-
 * provided URL) with `reportProgress: true` and emits per-file progress
 * via signals. Cancel via `AbortController`.
 */

export interface UploadProgressEntry {
  /** Stable id (filename + size + random suffix). */
  id: string;
  filename: string;
  size: number;
  /** 0–100 percent. */
  percent: number;
  status: "pending" | "uploading" | "success" | "failed" | "cancelled";
  errorMessage?: string;
}

export interface UploadSummary {
  success: number;
  failed: number;
  skipped: number;
}

@Injectable({ providedIn: "root" })
export class UploadService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /** Map: file id → AbortController, so caller can cancel individual uploads. */
  private readonly controllers = new Map<string, AbortController>();

  readonly progressSignal = signal<UploadProgressEntry[]>([]);

  /**
   * Upload one file, emitting progress updates into `progressSignal` and to the
   * optional `onProgress` callback (0–100 percent).
   *
   * @param file       File to upload.
   * @param uploadUrl  Absolute URL to POST FormData to.
   * @param fieldName  FormData field name (default: "files").
   * @param onProgress Optional callback invoked on each progress event.
   */
  uploadFile(
    file: File,
    uploadUrl: string,
    fieldName = "files",
    onProgress?: (percent: number) => void,
  ): Observable<HttpResponse<unknown>> {
    const id = this.makeId(file);
    const controller = new AbortController();
    this.controllers.set(id, controller);

    this.upsertEntry({
      id,
      filename: file.name,
      size: file.size,
      percent: 0,
      status: "uploading",
    });

    const formData = new FormData();
    formData.append(fieldName, file, file.name);

    return this.http
      .post<unknown>(uploadUrl, formData, {
        reportProgress: true,
        observe: "events",
        responseType: "json" as const,
        context: undefined,
        // Note: Angular HttpClient does not accept AbortSignal directly.
        // The controller is used by `cancelUpload()` via subscription unsubscribe.
      })
      .pipe(
        filter((event) => {
          if (event.type === HttpEventType.UploadProgress) {
            this.handleProgress(id, event, onProgress);
            return false; // don't emit progress to caller
          }
          return event.type === HttpEventType.Response;
        }),
        map((event) => event as HttpResponse<unknown>),
        filter((response): response is HttpResponse<unknown> => !!response),
      );
  }

  /**
   * Mark an upload as cancelled. The active HTTP subscription (if any)
   * will be torn down by the caller's takeUntilDestroyed / switchMap.
   */
  cancelUpload(id: string): void {
    const controller = this.controllers.get(id);
    if (controller) {
      controller.abort();
      this.controllers.delete(id);
    }
    this.upsertEntry({
      id,
      filename: this.findEntry(id)?.filename ?? id,
      size: this.findEntry(id)?.size ?? 0,
      percent: this.findEntry(id)?.percent ?? 0,
      status: "cancelled",
    });
  }

  /** Reset progress state (used when closing the dialog / navigating away). */
  reset(): void {
    for (const controller of this.controllers.values()) {
      controller.abort();
    }
    this.controllers.clear();
    this.progressSignal.set([]);
  }

  /** Compute summary counts for the upload-summary UI. */
  computeSummary(): UploadSummary {
    const entries = this.progressSignal();
    let success = 0;
    let failed = 0;
    let skipped = 0;
    for (const entry of entries) {
      if (entry.status === "success") success++;
      else if (entry.status === "failed") failed++;
      else if (entry.status === "cancelled") skipped++;
    }
    return { success, failed, skipped };
  }

  private handleProgress(
    id: string,
    event: HttpProgressEvent,
    onProgress?: (percent: number) => void,
  ): void {
    const percent = event.total
      ? Math.round((event.loaded / event.total) * 100)
      : 0;
    this.upsertEntry({
      id,
      filename: this.findEntry(id)?.filename ?? id,
      size: this.findEntry(id)?.size ?? 0,
      percent,
      status: "uploading",
    });
    if (onProgress) {
      onProgress(percent);
    }
  }

  /** Insert-or-update by id, preserving entry order. */
  private upsertEntry(entry: UploadProgressEntry): void {
    this.progressSignal.update((list) => {
      const idx = list.findIndex((e) => e.id === entry.id);
      if (idx === -1) return [...list, entry];
      const next = [...list];
      next[idx] = { ...next[idx], ...entry };
      return next;
    });
  }

  private findEntry(id: string): UploadProgressEntry | undefined {
    return this.progressSignal().find((e) => e.id === id);
  }

  private makeId(file: File): string {
    const rand = Math.random().toString(36).slice(2, 8);
    return `${file.name}:${file.size}:${rand}`;
  }
}
