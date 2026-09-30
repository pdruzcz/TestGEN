import { Component, inject, signal, computed, OnInit, DestroyRef } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { RouterLink, ActivatedRoute } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { NavbarComponent } from "../../../../../shared/components/navbar.component";
import { FooterComponent } from "../../../../../shared/components/footer.component";
import {
  GuiService,
  GUIScreenshot,
  VisualRegressionResponse,
  ComponentDelta,
  ChangeSeverity,
  ChangeType,
  VisualTestFramework,
} from "../../services/gui.service";

/**
 * Story 3.10: visual-regression comparison view. Lets the user pick a baseline +
 * comparison screenshot, run the comparison, inspect classified changes
 * (filterable by change type / severity), preview the annotated diff-image and
 * the generated Playwright / Cypress regression test code.
 */
@Component({
  selector: "app-gui-comparison",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatCheckboxModule,
    RouterLink,
    NavbarComponent,
    FooterComponent,
  ],
  templateUrl: "./gui-comparison.component.html",
  styleUrls: ["./gui-comparison.component.scss"],
})
export class GuiComparisonComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly guiService = inject(GuiService);

  readonly screenshots = signal<GUIScreenshot[]>([]);
  readonly baselineId = signal("");
  readonly comparisonId = signal("");
  readonly pixelThreshold = signal(0.02);
  readonly generateTestCode = signal(true);
  readonly testFramework = signal<VisualTestFramework>("playwright");

  readonly result = signal<VisualRegressionResponse | null>(null);
  readonly isLoading = signal(false);
  readonly isComparing = signal(false);
  readonly loadError = signal("");

  readonly severityFilter = signal<ChangeSeverity | "all">("all");
  readonly changeTypeFilter = signal<ChangeType | "all">("all");

  readonly projectId = computed(
    () => this.route.snapshot.paramMap.get("projectId") ?? "",
  );

  readonly filteredDeltas = computed<ComponentDelta[]>(() => {
    const res = this.result();
    if (!res) return [];
    const sev = this.severityFilter();
    const type = this.changeTypeFilter();
    return res.semanticDiff.filter(
      (d) =>
        (sev === "all" || d.severity === sev) &&
        (type === "all" || d.changeType === type),
    );
  });

  readonly diffImageSrc = computed(() => {
    const res = this.result();
    if (!res || !res.id || !res.diffImageUrl) return "";
    return this.guiService.diffImageUrl(this.projectId(), res.id);
  });

  ngOnInit(): void {
    if (this.projectId()) {
      this.loadScreenshots();
    }
  }

  private loadScreenshots(): void {
    this.isLoading.set(true);
    this.loadError.set("");
    this.guiService
      .listScreenshots(this.projectId(), 1, 100)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.screenshots.set(res.screenshots);
          this.isLoading.set(false);
        },
        error: (err) => {
          this.loadError.set(
            `Błąd ładowania screenshotów: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
          this.isLoading.set(false);
        },
      });
  }

  compare(): void {
    if (!this.baselineId() || !this.comparisonId()) {
      this.loadError.set("Wybierz screenshot baseline oraz porównawczy.");
      return;
    }
    this.isComparing.set(true);
    this.loadError.set("");
    this.result.set(null);
    this.guiService
      .compareScreenshots(
        this.projectId(),
        this.baselineId(),
        this.comparisonId(),
        this.pixelThreshold(),
        this.generateTestCode(),
        this.testFramework(),
      )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.result.set(res);
          this.isComparing.set(false);
        },
        error: (err) => {
          this.isComparing.set(false);
          this.loadError.set(
            `Błąd porównania: ${err?.error?.detail || err?.message || "Nieznany błąd"}`,
          );
        },
      });
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      match: "Zgodne",
      minor_diff: "Drobne różnice",
      major_diff: "Istotne różnice",
      error: "Błąd",
    };
    return map[status] ?? status;
  }

  changeTypeLabel(type: string): string {
    const map: Record<string, string> = {
      layout_change: "Zmiana układu",
      text_change: "Zmiana tekstu",
      color_change: "Zmiana koloru",
      element_added: "Dodano element",
      element_removed: "Usunięto element",
      element_moved: "Przesunięto element",
    };
    return map[type] ?? type;
  }

  severityLabel(severity: string): string {
    const map: Record<string, string> = {
      breaking: "Krytyczna",
      visual: "Wizualna",
      minor: "Drobna",
    };
    return map[severity] ?? severity;
  }
}
