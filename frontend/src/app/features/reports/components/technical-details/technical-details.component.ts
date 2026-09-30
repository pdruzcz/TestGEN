import { Component, input } from "@angular/core";
import { MatIconModule } from "@angular/material/icon";
import { CodeHighlighterComponent } from "../../../results/components/code-highlighter/code-highlighter.component";
import { ReportData, ReportFinding } from "../../services/report.service";

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Krytyczny",
  high: "Wysoki",
  medium: "Średni",
  low: "Niski",
};

const SOURCE_LABELS: Record<string, string> = {
  security: "Skan bezpieczeństwa",
  gap: "Analiza luk",
};

/**
 * AC3/AC5 — raport techniczny: pełna lista ustaleń z fragmentami kodu
 * (podświetlanie składni), severity, CWE/CVSS, rekomendacjami i
 * powiązaniami z plikami źródłowymi.
 */
@Component({
  selector: "app-technical-details",
  standalone: true,
  imports: [MatIconModule, CodeHighlighterComponent],
  templateUrl: "./technical-details.component.html",
  styleUrls: ["./technical-details.component.scss"],
})
export class TechnicalDetailsComponent {
  readonly data = input.required<ReportData>();

  readonly severityLabels = SEVERITY_LABELS;
  readonly sourceLabels = SOURCE_LABELS;

  location(f: ReportFinding): string | null {
    if (!f.filePath) return null;
    return f.lineStart ? `${f.filePath}:${f.lineStart}` : f.filePath;
  }
}
