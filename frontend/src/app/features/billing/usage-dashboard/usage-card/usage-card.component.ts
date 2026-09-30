import { Component, computed, inject, input, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";

import {
  BillingService,
  UsageDashboardCounter,
  UsageHistoryPoint,
  UsageResource,
} from "../../billing.service";
import { UsageChartComponent } from "../usage-chart/usage-chart.component";

/** Polskie nazwy zasobów (AC1) — kolejność wg macierzy CR#2, bez „Użytkownicy". */
const RESOURCE_LABELS: Record<UsageResource, string> = {
  analyses: "Analizy",
  testCases: "Przypadki testowe",
  storageBytes: "Storage",
  filesPerAnalysis: "Pliki na analizę",
};

/** Zakres historii pobierany po rozwinięciu karty (AC3). */
const HISTORY_DAYS = 30;

/**
 * Karta pojedynczego zasobu (Story 7.9, AC1): nazwa, „{N} / {limit}"
 * (lub „{N} — bez limitu"), pasek postępu z progiem koloru
 * (zielony <70%, żółty 70–90%, czerwony >90%) i rozwijane szczegóły
 * z wykresem historii (AC3). Rolą „progressbar" + aria — AC6.
 */
@Component({
  selector: "app-usage-card",
  imports: [
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    UsageChartComponent,
  ],
  templateUrl: "./usage-card.component.html",
  styleUrl: "./usage-card.component.scss",
})
export class UsageCardComponent {
  private readonly billing = inject(BillingService);

  readonly counter = input.required<UsageDashboardCounter>();

  readonly expanded = signal(false);
  readonly historyLoading = signal(false);
  readonly historyError = signal<string | null>(null);
  readonly historyPoints = signal<UsageHistoryPoint[]>([]);

  readonly label = computed(() => RESOURCE_LABELS[this.counter().type]);

  readonly isStorage = computed(() => this.counter().type === "storageBytes");

  /** „{N} / {limit}" / „{N} MB / {limit} MB" / „{N} — bez limitu" (AC1). */
  readonly valueLabel = computed(() => {
    const { value, limit } = this.counter();
    const unit = this.isStorage() ? " MB" : "";
    if (limit === null) {
      return `${displayValue(value, this.isStorage())}${unit} — bez limitu`;
    }
    return `${displayValue(value, this.isStorage())}${unit} / ${displayValue(limit, this.isStorage())}${unit}`;
  });

  /** Etykieta procentowa (AC6 — kolor nie jest jedynym nośnikiem informacji). */
  readonly pctLabel = computed(() => {
    const { percentage } = this.counter();
    return percentage === null ? "bez limitu" : `${percentage}%`;
  });

  /** Wartość paska (0–100); null → pasek ukryty (unlimited). */
  readonly barValue = computed(() => {
    const { percentage } = this.counter();
    return percentage === null ? null : Math.min(percentage, 100);
  });

  /** Próg koloru paska (AC1): zielony <70, żółty 70–90, czerwony >90. */
  readonly barState = computed<"ok" | "warn" | "danger">(() => {
    const p = this.counter().percentage;
    if (p === null || p < 70) {
      return "ok";
    }
    return p <= 90 ? "warn" : "danger";
  });

  readonly barAriaLabel = computed(
    () =>
      `Zużycie zasobu ${this.label()}: ${this.valueLabel()} (${this.pctLabel()})`,
  );

  /** Jednostka wartości dla wykresu/tabeli (storage w MB). */
  readonly chartValueUnit = computed(() => (this.isStorage() ? " MB" : ""));

  /** ID sekcji szczegółów (aria-controls przycisku rozwinięcia). */
  readonly detailsId = computed(() => `usage-details-${this.counter().type}`);

  /** AC3 — rozwinięcie karty: leniwe pobranie historii przy pierwszym razie. */
  toggle(): void {
    const next = !this.expanded();
    this.expanded.set(next);
    if (next && this.historyPoints().length === 0 && !this.historyLoading()) {
      this.loadHistory();
    }
  }

  loadHistory(): void {
    this.historyError.set(null);
    this.historyLoading.set(true);
    this.billing.getUsageHistory(this.counter().type, HISTORY_DAYS).subscribe({
      next: (history) => {
        this.historyPoints.set(history.points);
        this.historyLoading.set(false);
      },
      error: () => {
        this.historyLoading.set(false);
        this.historyError.set(
          "Nie udało się pobrać historii zużycia. Spróbuj ponownie za chwilę.",
        );
      },
    });
  }
}

/** storage_bytes → MB (zaokrąglone), pozostałe liczniki bez konwersji. */
function displayValue(value: number, isStorage: boolean): string {
  if (!isStorage) {
    return String(value);
  }
  return String(Math.round(value / (1024 * 1024)));
}
