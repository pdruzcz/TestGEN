import { Component, computed, input } from "@angular/core";

import { UsageHistoryPoint } from "../../billing.service";

/** Geometria wykresu — stała przestrzeń SVG (wzorzec ChartRenderingService). */
const WIDTH = 560;
const HEIGHT = 200;
const PADDING = 8;

/** Punkt na płaszczyźnie SVG z etykietą dnia (oś X). */
interface ChartPoint {
  x: number;
  y: number;
  label: string;
  value: number;
  date: string;
}

/**
 * Wykres liniowy zużycia skumulowanego vs limit (Story 7.9, AC3).
 *
 * Natywne SVG bez zewnętrznych bibliotek (konwencja projektu — brak
 * Chart.js w zależnościach, wzorzec reports/ChartRenderingService):
 * linia zużycia + przerywana czerwona linia limitu + siatka wartości.
 * Alternatywa tekstowa (tabela danych) — AC6/WCAG 2.1 AA.
 */
@Component({
  selector: "app-usage-chart",
  imports: [],
  templateUrl: "./usage-chart.component.html",
  styleUrl: "./usage-chart.component.scss",
})
export class UsageChartComponent {
  /** Punkty historii (skumulowane zużycie na dzień, rosnąco po dacie). */
  readonly points = input<UsageHistoryPoint[]>([]);
  /** Limit planu (null = unlimited — bez linii limitu). */
  readonly limit = input<number | null>(null);
  /** Jednostka wartości w tabeli alternatywnej (np. " MB"). */
  readonly valueUnit = input<string>("");

  readonly width = WIDTH;
  readonly height = HEIGHT;

  /** Punkty przeskalowane na płaszczyznę SVG (x równomiernie, y = wartość). */
  readonly chartPoints = computed<ChartPoint[]>(() => {
    const points = this.points();
    const max = this.scaleMax();
    const n = points.length;
    const innerW = WIDTH - PADDING * 2;
    const innerH = HEIGHT - PADDING * 2;
    return points.map((p, i) => ({
      x: PADDING + (n > 1 ? (i / (n - 1)) * innerW : innerW / 2),
      y: PADDING + innerH - (Math.min(p.value, max) / max) * innerH,
      label: formatDate(p.date),
      value: p.value,
      date: p.date,
    }));
  });

  /** Ścieżka polyline zużycia (atribut d). */
  readonly linePath = computed<string>(() =>
    this.chartPoints()
      .map(
        (p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`,
      )
      .join(" "),
  );

  /** Poziome linie siatki z etykietami wartości (0 / 50 / 100% skali). */
  readonly gridLines = computed<{ y: number; value: number }[]>(() => {
    const max = this.scaleMax();
    const innerH = HEIGHT - PADDING * 2;
    return [0, 0.5, 1].map((f) => ({
      y: PADDING + innerH - f * innerH,
      value: Math.round(max * f),
    }));
  });

  /** Y przerywanej linii limitu (null gdy unlimited lub limit poza skalą). */
  readonly limitLineY = computed<number | null>(() => {
    const limit = this.limit();
    if (limit === null) {
      return null;
    }
    const max = this.scaleMax();
    const innerH = HEIGHT - PADDING * 2;
    return PADDING + innerH - (Math.min(limit, max) / max) * innerH;
  });

  /** Etykiety osi X — pierwszy, środkowy i ostatni dzień (bez tłoku). */
  readonly xLabels = computed<{ x: number; label: string }[]>(() => {
    const pts = this.chartPoints();
    if (pts.length === 0) {
      return [];
    }
    const mid = pts[Math.floor((pts.length - 1) / 2)];
    const picked = [pts[0], mid, pts[pts.length - 1]];
    const unique = picked.filter((p, i) => i === 0 || p.x !== picked[i - 1].x);
    return unique.map((p) => ({ x: p.x, label: p.label }));
  });

  /** Czy jest wystarczająco danych, aby narysować linię (min. 2 punkty). */
  readonly hasLine = computed(() => this.points().length >= 2);

  /** aria-label wykresu (AC6 — tekstowa informacja o zawartości SVG). */
  readonly ariaLabel = computed(() => {
    const pts = this.points();
    const limit = this.limit();
    const range =
      pts.length > 0
        ? `od ${formatDate(pts[0].date)} do ${formatDate(pts[pts.length - 1].date)}`
        : "brak danych";
    const last =
      pts.length > 0
        ? `, ostatnio ${pts[pts.length - 1].value}${this.valueUnit()}`
        : "";
    const limitInfo =
      limit !== null ? `, limit ${limit}${this.valueUnit()}` : ", bez limitu";
    return `Wykres liniowy skumulowanego zużycia (${range}${last}${limitInfo}). Dane w tabeli poniżej.`;
  });

  private scaleMax(): number {
    const peak = this.points().reduce((m, p) => Math.max(m, p.value), 0);
    const limit = this.limit();
    // Skala zawsze pokazuje linię limitu w całości (o ile jest limit).
    return Math.max(peak, limit ?? 0, 1);
  }
}

/** "2026-09-10" → "10.09" (etykieta osi X). */
function formatDate(iso: string): string {
  const day = iso.slice(8, 10);
  const month = iso.slice(5, 7);
  return `${day}.${month}`;
}
