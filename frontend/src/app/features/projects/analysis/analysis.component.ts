import {
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSnackBar, MatSnackBarModule } from "@angular/material/snack-bar";
import { NavbarComponent } from "../../../shared/components/navbar.component";
import { FooterComponent } from "../../../shared/components/footer.component";
import {
  AnalysisConfig,
  AnalysisService,
  DEFAULT_ANALYSIS_CONFIG,
  TaskStatusResponse,
} from "../services/analysis.service";
import { PreprocessingService } from "../services/preprocessing.service";
import { ConfigService } from "../../../core/services/config.service";
import { AnalysisConfigFormComponent } from "./components/analysis-config-form/analysis-config-form.component";

type TaskState = "idle" | "starting" | "running" | "completed" | "failed" | "cancelled";

const STEP_LABELS: Record<string, string> = {
  queued: "Kolejkowanie",
  preprocessing: "Parsowanie",
  ast_parsing: "Parsowanie",
  analysis: "Analiza",
  test_generation: "Generowanie testów",
  code_generation: "Generowanie testów",
  export: "Finalizacja",
};

const TERMINAL_STATES = ["completed", "failed", "timeout", "partial_failure", "cancelled"];

@Component({
  selector: "app-analysis",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    NavbarComponent,
    FooterComponent,
    AnalysisConfigFormComponent,
  ],
  templateUrl: "./analysis.component.html",
  styleUrls: ["./analysis.component.scss"],
})
export class AnalysisComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly analysisService = inject(AnalysisService);
  private readonly preprocessingService = inject(PreprocessingService);
  private readonly configService = inject(ConfigService);
  private readonly snackBar = inject(MatSnackBar);

  /**
   * Ostatni stan formularza konfiguracji. Utrzymywanie go tutaj pozwala
   * przyciskowi "Uruchom analizę" żyć poza formularzem (AC3) i sterować
   * jego stanem `disabled` na podstawie wybranych modułów.
   */
  readonly currentConfig = signal<AnalysisConfig>(DEFAULT_ANALYSIS_CONFIG);

  // --- Task state signals ---
  readonly taskState = signal<TaskState>("idle");
  readonly taskProgress = signal(0);
  readonly currentStep = signal("");
  readonly errorMessage = signal("");
  readonly currentTaskId = signal<string | null>(null);
  readonly cancelling = signal(false);

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  // Stats from preprocessing report
  readonly fileCount = computed(() => {
    const report = this.preprocessingService.reportSignal();
    if (!report) return "-";
    return report.languages.reduce((sum: number, ls: any) => sum + ls.count, 0).toString();
  });
  readonly totalLoc = computed(() => {
    const report = this.preprocessingService.reportSignal();
    if (!report) return "-";
    return report.totalLoc.toLocaleString("pl-PL");
  });
  readonly languages = computed(
    () => this.preprocessingService.reportSignal()?.languages ?? [],
  );
  readonly frameworks = computed(
    () => this.preprocessingService.reportSignal()?.detectedFrameworks ?? [],
  );

  private pollingInterval: ReturnType<typeof setInterval> | null = null;

  readonly stepLabel = computed(
    () => STEP_LABELS[this.currentStep()] ?? this.currentStep(),
  );
  readonly buttonLabel = computed(() => {
    switch (this.taskState()) {
      case "starting":
        return "Uruchamianie...";
      case "running":
        return "Analiza w toku...";
      case "completed":
        return "Uruchom ponownie";
      case "failed":
      case "cancelled":
        return "Spróbuj ponownie";
      default:
        return "Uruchom analizę";
    }
  });

  ngOnInit(): void {
    this.destroyRef.onDestroy(() => this.stopPolling());
    this.configService.loadConfig();
    this.preprocessingService.loadReport(this.projectId());
  }

  // --- Analysis actions (AC3, AC5, AC6, AC7) ---

  /** Track the latest form state without re-triggering the backend. */
  onConfigChange(cfg: AnalysisConfig): void {
    this.currentConfig.set(cfg);
  }

  /** Story 6.3 AC3 — start analysis with the supplied config. */
  startAnalysis(cfg: AnalysisConfig = this.currentConfig()): void {
    this.taskState.set("starting");
    this.errorMessage.set("");

    this.analysisService.startProjectAnalysis(this.projectId(), cfg).subscribe({
      next: (res) => {
        this.taskState.set("running");
        this.currentTaskId.set(res.taskId);
        this.startPolling(res.taskId);
      },
      error: (err) => {
        this.taskState.set("failed");
        this.errorMessage.set(this.extractErrorMessage(err));
        this.snackBar.open("Nie udało się uruchomić analizy.", "OK", {
          duration: 4000,
        });
      },
    });
  }

  cancelAnalysis(): void {
    const taskId = this.currentTaskId();
    if (!taskId) return;

    this.cancelling.set(true);
    this.analysisService.cancelTask(taskId).subscribe({
      next: () => {
        this.cancelling.set(false);
        this.stopPolling();
        this.taskState.set("cancelled");
        this.snackBar.open("Analiza została anulowana.", "OK", { duration: 4000 });
      },
      error: () => {
        this.cancelling.set(false);
        // Zgłoś błąd, ale nie przerywaj pollingu — backend i tak poda stan końcowy.
        this.snackBar.open(
          "Nie udało się anulować analizy. Spróbuj ponownie.",
          "OK",
          { duration: 4000 },
        );
      },
    });
  }

  private startPolling(taskId: string): void {
    this.stopPolling();
    this.pollingInterval = setInterval(() => {
      this.analysisService.getTaskStatus(taskId).subscribe({
        next: (res: TaskStatusResponse) => {
          this.taskProgress.set(res.progress);
          this.currentStep.set(res.currentStep);

          if (TERMINAL_STATES.includes(res.status)) {
            this.stopPolling();
            this.handleTerminalState(res);
          }
        },
        error: () => {
          // Transient network error — keep polling
        },
      });
    }, 5000);
  }

  private stopPolling(): void {
    if (this.pollingInterval !== null) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  private handleTerminalState(res: TaskStatusResponse): void {
    if (res.status === "completed") {
      this.taskState.set("completed");
      this.taskProgress.set(100);
      this.preprocessingService.loadReport(this.projectId());
      this.snackBar.open("Analiza zakończona pomyślnie!", "Pokaż wyniki", {
        duration: 6000,
      });
    } else if (res.status === "cancelled") {
      this.taskState.set("cancelled");
    } else {
      // failed / timeout / partial_failure — Story 6.3 AC7
      this.taskState.set("failed");
      this.errorMessage.set(
        res.error ?? `Analiza nie powiodła się (status: ${res.status})`,
      );
      this.snackBar.open(`Błąd analizy: ${res.error ?? res.status}`, "OK", {
        duration: 6000,
      });
    }
  }

  private extractErrorMessage(err: any): string {
    if (err?.error?.type?.includes("quota-exceeded") || err?.status === 429) {
      const plan = err?.error?.plan ?? "basic";
      const limit = err?.error?.limit ?? 10;
      return `Osiągnięto miesięczny limit analiz (${limit}) dla planu ${plan}. Zwiększ plan, aby kontynuować.`;
    }
    if (err?.error?.detail) return err.error.detail;
    if (err?.message) return err.message;
    return "Wystąpił nieoczekiwany błąd.";
  }
}
