import { HttpClient } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, throwError, timer } from "rxjs";
import { catchError, filter, map, switchMap, take, tap } from "rxjs/operators";
import { environment } from "../../../../environments/environment";
import { ReportData, ReportType } from "./report.service";

export type ExportFormat = "pdf" | "html" | "csv" | "xlsx" | "json" | "yaml";

export const EXPORT_FORMAT_LABELS: Record<ExportFormat, string> = {
  pdf: "PDF",
  html: "HTML",
  csv: "CSV",
  xlsx: "Excel",
  json: "JSON",
  yaml: "YAML",
};

export interface ExportRequestResponse {
  exportId: string;
  status: string;
}

export interface ExportStatus {
  exportId: string;
  status: "pending" | "done" | "error";
  exportFormat: ExportFormat;
  filename: string;
  error: string | null;
}

/** Interwał odpytywania o status generowania (AC1). */
export const EXPORT_POLL_INTERVAL_MS = 3000;

/**
 * Story 6.7 — eksport raportów w 6 formatach. BE generuje plik
 * asynchronicznie (zapis do MinIO na 7 dni — AC7); FE odpytuje status co 3s
 * i po zakończeniu pobiera plik (Content-Disposition — AC8).
 */
@Injectable({ providedIn: "root" })
export class ExportService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  readonly activeFormatSignal = signal<ExportFormat | null>(null);
  readonly exportStatusSignal = signal<"idle" | "pending" | "done" | "error">(
    "idle",
  );

  requestExport(
    projectId: string,
    format: ExportFormat,
    reportType: ReportType,
    report: ReportData,
  ): Observable<ExportRequestResponse> {
    return this.http.post<ExportRequestResponse>(
      `${this.apiUrl}/projects/${projectId}/reports/export`,
      { format, reportType, report },
    );
  }

  getExportStatus(exportId: string): Observable<ExportStatus> {
    return this.http.get<ExportStatus>(
      `${this.apiUrl}/exports/${exportId}/status`,
    );
  }

  downloadExport(exportId: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/exports/${exportId}/download`, {
      responseType: "blob",
    });
  }

  /**
   * Pełny przebieg eksportu: zlecenie → polling co 3s → pobranie pliku.
   * Emituje nazwę pobranego pliku i kończy strumień.
   */
  exportReport(
    projectId: string,
    format: ExportFormat,
    reportType: ReportType,
    report: ReportData,
  ): Observable<string> {
    this.activeFormatSignal.set(format);
    this.exportStatusSignal.set("pending");

    return this.requestExport(projectId, format, reportType, report).pipe(
      switchMap((res) =>
        timer(0, EXPORT_POLL_INTERVAL_MS).pipe(
          switchMap(() => this.getExportStatus(res.exportId)),
          filter((status) => status.status !== "pending"),
          take(1),
          map((status) => ({ status, exportId: res.exportId })),
        ),
      ),
      switchMap(({ status, exportId }) => {
        if (status.status === "error") {
          return throwError(
            () => new Error(status.error ?? "Eksport nie powiódł się"),
          );
        }
        return this.downloadExport(exportId).pipe(
          map((blob) => {
            this.saveBlob(blob, status.filename);
            return status.filename;
          }),
        );
      }),
      tap(() => {
        this.exportStatusSignal.set("done");
        this.activeFormatSignal.set(null);
      }),
      catchError((err) => {
        this.exportStatusSignal.set("error");
        this.activeFormatSignal.set(null);
        return throwError(() => err);
      }),
    );
  }

  /** Automatyczne pobranie pliku po stronie przeglądarki (AC8). */
  protected saveBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }
}
