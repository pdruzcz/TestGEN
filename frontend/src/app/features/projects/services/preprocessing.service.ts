import { HttpClient } from "@angular/common/http";
import { inject, Injectable, signal } from "@angular/core";
import { environment } from "../../../../environments/environment";

export interface LanguageStat {
  language: string;
  count: number;
  loc: number;
}

export interface UnknownFile {
  filename: string;
  fileId: string;
}

export interface PreprocessingReport {
  projectId: string;
  languages: LanguageStat[];
  detectedFrameworks: string[];
  totalLoc: number;
  unknownFiles: UnknownFile[];
}

export interface PreprocessingTask {
  taskId: string;
  status: string;
  statusUrl: string;
}

@Injectable({ providedIn: "root" })
export class PreprocessingService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiUrl}/projects`;

  readonly reportSignal = signal<PreprocessingReport | null>(null);
  readonly isLoadingSignal = signal(false);
  readonly errorSignal = signal("");

  private pollingIntervalId: ReturnType<typeof setInterval> | null = null;
  private pollingTimeoutId: ReturnType<typeof setTimeout> | null = null;

  triggerPreprocessing(projectId: string) {
    this.cancelPolling();
    this.isLoadingSignal.set(true);
    this.errorSignal.set("");
    this.http
      .post<PreprocessingTask>(`${this.apiUrl}/${projectId}/preprocess`, {})
      .subscribe({
        next: () => {
          this.pollReport(projectId);
        },
        error: () => {
          this.isLoadingSignal.set(false);
          this.errorSignal.set(
            "Nie udało się uruchomić preprocessingu. Spróbuj ponownie.",
          );
        },
      });
  }

  loadReport(projectId: string) {
    this.isLoadingSignal.set(true);
    this.errorSignal.set("");
    this.http
      .get<PreprocessingReport>(
        `${this.apiUrl}/${projectId}/preprocessing-report`,
      )
      .subscribe({
        next: (report) => {
          this.reportSignal.set(report);
          this.isLoadingSignal.set(false);
        },
        error: () => {
          this.reportSignal.set(null);
          this.isLoadingSignal.set(false);
        },
      });
  }

  classifyFile(
    projectId: string,
    fileId: string,
    data: { detectedLanguage?: string; detectedFramework?: string },
  ) {
    return this.http.patch(
      `${this.apiUrl}/${projectId}/source-files/${fileId}`,
      data,
    );
  }

  cancelPolling(): void {
    if (this.pollingIntervalId) {
      clearInterval(this.pollingIntervalId);
      this.pollingIntervalId = null;
    }
    if (this.pollingTimeoutId) {
      clearTimeout(this.pollingTimeoutId);
      this.pollingTimeoutId = null;
    }
  }

  private pollReport(projectId: string) {
    this.cancelPolling();

    this.pollingIntervalId = setInterval(() => {
      this.http
        .get<PreprocessingReport>(
          `${this.apiUrl}/${projectId}/preprocessing-report`,
        )
        .subscribe({
          next: (report) => {
            this.reportSignal.set(report);
            this.isLoadingSignal.set(false);
            this.cancelPolling();
          },
          error: () => {
            // Report not ready yet, keep polling
          },
        });
    }, 3000);

    this.pollingTimeoutId = setTimeout(() => {
      this.cancelPolling();
      if (this.isLoadingSignal()) {
        this.isLoadingSignal.set(false);
        this.errorSignal.set(
          "Preprocessing trwa zbyt długo. Odśwież stronę za chwilę.",
        );
      }
    }, 60000);
  }
}
