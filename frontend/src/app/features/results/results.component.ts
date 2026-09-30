import { Component, OnInit, computed, inject, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatTabsModule } from "@angular/material/tabs";
import { NavbarComponent } from "../../shared/components/navbar.component";
import { FooterComponent } from "../../shared/components/footer.component";
import { LockedFeatureTabComponent } from "../../shared/components/locked-feature-tab/locked-feature-tab.component";
import { LockedModuleComponent } from "../../shared/components/locked-module/locked-module.component";
import { ModuleLocksService } from "../../core/services/module-locks.service";
import {
  FilterPanelComponent,
  SEVERITY_LABELS,
  STATUS_LABELS,
} from "./components/filter-panel/filter-panel.component";
import { ResultDetailComponent } from "./components/result-detail/result-detail.component";
import {
  ResultItem,
  ResultSeverity,
  ResultStatus,
  ResultsService,
  ResultsSort,
} from "./services/results.service";

const SEVERITY_ICONS: Record<ResultSeverity, string> = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "arrow_downward",
};

const SEVERITY_ORDER: readonly ResultSeverity[] = [
  "critical",
  "high",
  "medium",
  "low",
];

/**
 * Story 6.4 — przeglądarka wyników analizy. AC1: zakładki Przegląd /
 * Przypadki testowe / Bezpieczeństwo / Luki / Pokrycie / Raport
 * (MatTabGroup). AC8: nawigacja klawiaturą — MatTabGroup natywnie
 * obsługuje Tab/Enter/strzałki na zakładkach; strzałki na listach
 * wyników obsługiwane przez onListKeydown (roving focus).
 */
@Component({
  selector: "app-results",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTabsModule,
    NavbarComponent,
    FooterComponent,
    LockedFeatureTabComponent,
    LockedModuleComponent,
    FilterPanelComponent,
    ResultDetailComponent,
  ],
  templateUrl: "./results.component.html",
  styleUrls: ["./results.component.scss"],
})
export class ResultsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  readonly resultsService = inject(ResultsService);

  /** Story 7.13 — blokady modułów gated (widoczne-zablokowane, signals). */
  readonly locks = inject(ModuleLocksService);

  readonly severityLabels = SEVERITY_LABELS;
  readonly statusLabels = STATUS_LABELS;
  readonly severityIcons = SEVERITY_ICONS;
  readonly severityOrder = SEVERITY_ORDER;

  /**
   * Akcesory zamiast indeksowania map w szablonie — wiersze tabeli
   * pochodzą z nietypowanego kontekstu `ngTemplateOutlet` (`let-items`),
   * więc bezpośrednie `severityIcons[item.severity]` daje TS7053.
   */
  severityIcon(severity: ResultSeverity): string {
    return SEVERITY_ICONS[severity];
  }

  severityLabel(severity: ResultSeverity): string {
    return SEVERITY_LABELS[severity];
  }

  statusLabel(status: ResultStatus): string {
    return STATUS_LABELS[status];
  }

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly selectedResult = signal<ResultItem | null>(null);
  readonly testCaseSearch = signal("");

  readonly securityResults = computed(() =>
    this.resultsService
      .sortedResultsComputed()
      .filter((r) => r.source === "security"),
  );
  readonly gapResults = computed(() =>
    this.resultsService
      .sortedResultsComputed()
      .filter((r) => r.source === "gap"),
  );

  readonly filteredTestCases = computed(() => {
    const query = this.testCaseSearch().trim().toLowerCase();
    const cases = this.resultsService.testCaseService.testCasesSignal();
    if (!query) return cases;
    return cases.filter(
      (tc) =>
        tc.title.toLowerCase().includes(query) ||
        (tc.description ?? "").toLowerCase().includes(query),
    );
  });

  readonly severityCounts = computed(() => {
    const counts: Record<ResultSeverity, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    };
    for (const item of this.resultsService.resultsSignal()) {
      counts[item.severity]++;
    }
    return counts;
  });

  ngOnInit(): void {
    const projectId = this.projectId();
    this.resultsService.loadResults(projectId).subscribe();
    this.resultsService.loadOverview(projectId);
    this.locks.ensureLoaded();
  }

  onTabChange(index: number): void {
    this.resultsService.activeTabSignal.set(index);
    this.selectedResult.set(null);
  }

  selectResult(item: ResultItem): void {
    this.selectedResult.set(
      this.selectedResult()?.id === item.id ? null : item,
    );
  }

  onSort(column: ResultsSort["column"]): void {
    this.resultsService.toggleSort(column);
  }

  sortIndicator(column: ResultsSort["column"]): string {
    const sort = this.resultsService.sortSignal();
    if (sort.column !== column) return "";
    return sort.direction === "asc" ? "arrow_upward" : "arrow_downward";
  }

  ariaSort(column: ResultsSort["column"]): string {
    const sort = this.resultsService.sortSignal();
    if (sort.column !== column) return "none";
    return sort.direction === "asc" ? "ascending" : "descending";
  }

  /** AC8 — strzałki nawigują po wierszach wyników, Enter/Spacja otwiera szczegóły. */
  onListKeydown(event: KeyboardEvent): void {
    const target = event.target as HTMLElement;
    if (!target.classList.contains("result-row")) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const rows = Array.from(
        target
          .closest(".results-table-body")
          ?.querySelectorAll<HTMLElement>(".result-row") ?? [],
      );
      const idx = rows.indexOf(target);
      const next = event.key === "ArrowDown" ? idx + 1 : idx - 1;
      rows[next]?.focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      target.click();
    }
  }

  onTestCaseSearch(value: string): void {
    this.testCaseSearch.set(value);
  }

  complianceScoreClass(score: number): string {
    if (score >= 80) return "score-good";
    if (score >= 50) return "score-fair";
    return "score-poor";
  }
}
