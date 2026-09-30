import {
  Component,
  DestroyRef,
  computed,
  inject,
  input,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatCardModule } from "@angular/material/card";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import {
  SecurityDashboard,
  SecurityScanService,
} from "../../services/security-scan.service";

/**
 * Story 4.8: risk dashboard. Loads the CVSS-scored, prioritised assessment for
 * the project and renders the CVSS distribution histogram, the top 10 threats
 * and the recommended repair sequence (severity × effort).
 */
@Component({
  selector: "app-risk-dashboard",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: "./risk-dashboard.component.html",
  styleUrls: ["./risk-dashboard.component.scss"],
})
export class RiskDashboardComponent {
  private readonly service = inject(SecurityScanService);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = input.required<string>();

  readonly dashboard = signal<SecurityDashboard | null>(null);
  readonly isLoading = signal(false);
  readonly errorMessage = signal<string | null>(null);

  private readonly bands = ["critical", "high", "medium", "low", "info"];
  private readonly bandLabels: Record<string, string> = {
    critical: "Krytyczne",
    high: "Wysokie",
    medium: "Średnie",
    low: "Niskie",
    info: "Info",
  };

  readonly distribution = computed(() => {
    const dist = this.dashboard()?.cvssDistribution ?? {};
    const max = Math.max(1, ...this.bands.map((b) => dist[b] ?? 0));
    return this.bands.map((band) => ({
      band,
      label: this.bandLabels[band],
      value: dist[band] ?? 0,
      percent: Math.round(((dist[band] ?? 0) / max) * 100),
    }));
  });

  readonly effortLabels: Record<string, string> = {
    low: "Niski",
    medium: "Średni",
    high: "Wysoki",
  };

  load(): void {
    if (!this.projectId()) return;
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.service
      .getDashboard(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.dashboard.set(res);
          this.isLoading.set(false);
        },
        error: () => {
          this.errorMessage.set("Nie udało się pobrać dashboardu ryzyka.");
          this.isLoading.set(false);
        },
      });
  }
}
