import { Component, inject, input, signal } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { SecurityScanService } from "../../../projects/security/services/security-scan.service";
import { ResultItem, ResultSeverity } from "../../services/results.service";
import { CodeHighlighterComponent } from "../code-highlighter/code-highlighter.component";
import { DiffViewerComponent } from "../diff-viewer/diff-viewer.component";
import { SEVERITY_LABELS, STATUS_LABELS } from "../filter-panel/filter-panel.component";

/** AC7 — severity oznaczone kolorem ORAZ ikoną ORAZ tekstem (WCAG 2.1 AA). */
const SEVERITY_ICONS: Record<ResultSeverity, string> = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "arrow_downward",
};

/**
 * Szczegóły wyniku: tytuł, opis, severity (ikona + tekst + kolor),
 * lokalizacja, fragment kodu z podświetlaniem (AC5) i diff viewer (AC6).
 */
@Component({
  selector: "app-result-detail",
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    CodeHighlighterComponent,
    DiffViewerComponent,
  ],
  templateUrl: "./result-detail.component.html",
  styleUrls: ["./result-detail.component.scss"],
})
export class ResultDetailComponent {
  private readonly securityService = inject(SecurityScanService);

  readonly item = input.required<ResultItem>();
  readonly projectId = input.required<string>();

  readonly severityLabels = SEVERITY_LABELS;
  readonly statusLabels = STATUS_LABELS;
  readonly severityIcons = SEVERITY_ICONS;

  // Diff dla security finding — pobierany na żądanie z patch preview (Story 4.11).
  readonly diffOriginal = signal<string | null>(null);
  readonly diffFixed = signal<string | null>(null);
  readonly isDiffLoading = signal(false);
  readonly diffError = signal("");

  loadPatchPreview(): void {
    const item = this.item();
    if (item.source !== "security") return;
    this.isDiffLoading.set(true);
    this.diffError.set("");
    this.securityService.previewPatch(this.projectId(), item.id).subscribe({
      next: (preview) => {
        this.diffOriginal.set(preview.originalCode);
        this.diffFixed.set(preview.fixedCode);
        this.isDiffLoading.set(false);
      },
      error: () => {
        this.isDiffLoading.set(false);
        this.diffError.set(
          "Brak dostępnej poprawki dla tego wyniku. Wygeneruj patch w module bezpieczeństwa.",
        );
      },
    });
  }

  resetDiff(): void {
    this.diffOriginal.set(null);
    this.diffFixed.set(null);
    this.diffError.set("");
  }
}
