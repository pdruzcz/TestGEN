import { Component, computed, inject, input } from "@angular/core";
import { DatePipe, DecimalPipe } from "@angular/common";
import { MatIconModule } from "@angular/material/icon";
import {
  BarChartModel,
  ChartRenderingService,
  DonutChartModel,
  LineChartModel,
} from "../../services/chart-rendering.service";
import { ReportData } from "../../services/report.service";

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Krytyczne",
  high: "Ważne",
  medium: "Umiarkowane",
  low: "Drobne",
};

/**
 * AC2/AC4/AC6 — podsumowanie wykonawcze: KPI, wykresy (compliance per moduł,
 * trend, rozkład problemów), kluczowe wnioski prostym językiem polskim.
 * Wykresy jako natywne SVG z pattern fills (WCAG 2.1 AA).
 */
@Component({
  selector: "app-executive-summary",
  standalone: true,
  imports: [DatePipe, DecimalPipe, MatIconModule],
  templateUrl: "./executive-summary.component.html",
  styleUrls: ["./executive-summary.component.scss"],
})
export class ExecutiveSummaryComponent {
  private readonly charts = inject(ChartRenderingService);

  readonly data = input.required<ReportData>();

  readonly moduleChart = computed<BarChartModel>(() =>
    this.charts.buildBarChart(
      this.data().moduleScores.map((m) => ({
        label: this.moduleLabel(m.filePath),
        value: Math.round(m.score),
      })),
      { max: 100 },
    ),
  );

  readonly trendChart = computed<LineChartModel>(() =>
    this.charts.buildLineChart(
      this.data().trendPoints.map((p, i) => ({
        label: p.label ?? `Analiza ${i + 1}`,
        value: Math.round(p.score),
      })),
    ),
  );

  readonly severityChart = computed<DonutChartModel>(() => {
    const counts = this.data().severityCounts;
    return this.charts.buildDonutChart(
      (["critical", "high", "medium", "low"] as const).map((sev) => ({
        label: SEVERITY_LABELS[sev],
        value: counts[sev],
        colorClass: `sev-${sev}`,
      })),
    );
  });

  private moduleLabel(filePath: string): string {
    const parts = filePath.split(/[\\/]/);
    return parts[parts.length - 1] || filePath;
  }
}
