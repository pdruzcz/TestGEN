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
import { FindingsListComponent } from "../findings-list/findings-list.component";
import { PatchesListComponent } from "../patches-list/patches-list.component";
import {
  SecurityReport,
  SecurityScanService,
} from "../../services/security-scan.service";

/**
 * Story 4.7: aggregated security dashboard. Loads the consolidated report
 * (dedup + correlation + confidence) for the project and shows per-severity
 * summary cards plus the filterable findings list.
 *
 * Story 4.11: also exposes the project-wide security patches list
 * (batch patch generation + conflict detection).
 */
@Component({
  selector: "app-security-report",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    FindingsListComponent,
    PatchesListComponent,
  ],
  templateUrl: "./security-report.component.html",
  styleUrls: ["./security-report.component.scss"],
})
export class SecurityReportComponent {
  private readonly service = inject(SecurityScanService);
  private readonly destroyRef = inject(DestroyRef);

  readonly projectId = input.required<string>();

  readonly report = signal<SecurityReport | null>(null);
  readonly isLoading = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly severityCards = computed(() => {
    const counts = this.report()?.summary.severityCounts ?? {};
    return [
      { key: "critical", label: "Krytyczne", value: counts["critical"] ?? 0 },
      { key: "high", label: "Wysokie", value: counts["high"] ?? 0 },
      { key: "medium", label: "Średnie", value: counts["medium"] ?? 0 },
      { key: "low", label: "Niskie", value: counts["low"] ?? 0 },
    ];
  });

  load(): void {
    if (!this.projectId()) return;
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.service
      .getReport(this.projectId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.report.set(res);
          this.isLoading.set(false);
        },
        error: () => {
          this.errorMessage.set("Nie udało się pobrać raportu bezpieczeństwa.");
          this.isLoading.set(false);
        },
      });
  }
}
