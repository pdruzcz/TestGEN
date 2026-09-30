import { Injectable } from "@angular/core";

/**
 * AC6 — identyfikatory wzorków SVG (pattern fill) przypisywane cyklicznie
 * do serii danych. Każdy wykres rozróżnia serie wzorkiem ORAZ kolorem
 * (WCAG 2.1 AA — informacja nie może być przekazana wyłącznie kolorem).
 */
export const PATTERN_IDS = [
  "pat-stripes",
  "pat-dots",
  "pat-hatch",
  "pat-cross",
  "pat-vertical",
] as const;

export interface BarChartBar {
  label: string;
  value: number;
  x: number;
  y: number;
  width: number;
  height: number;
  patternId: string;
  colorClass: string;
}

export interface BarChartModel {
  width: number;
  height: number;
  bars: BarChartBar[];
}

export interface LineChartPoint {
  label: string;
  value: number;
  x: number;
  y: number;
}

export interface LineChartModel {
  width: number;
  height: number;
  path: string;
  areaPath: string;
  points: LineChartPoint[];
  gridLines: { y: number; value: number }[];
}

export interface DonutSegment {
  label: string;
  value: number;
  percentage: number;
  path: string;
  patternId: string;
  colorClass: string;
}

export interface DonutChartModel {
  size: number;
  segments: DonutSegment[];
  total: number;
}

function polarToCartesian(
  cx: number,
  cy: number,
  radius: number,
  angleDeg: number,
): { x: number; y: number } {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) };
}

function donutSegmentPath(
  cx: number,
  cy: number,
  outerR: number,
  innerR: number,
  startAngle: number,
  endAngle: number,
): string {
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  const so = polarToCartesian(cx, cy, outerR, startAngle);
  const eo = polarToCartesian(cx, cy, outerR, endAngle);
  const si = polarToCartesian(cx, cy, innerR, endAngle);
  const ei = polarToCartesian(cx, cy, innerR, startAngle);
  return [
    `M ${so.x.toFixed(2)} ${so.y.toFixed(2)}`,
    `A ${outerR} ${outerR} 0 ${largeArc} 1 ${eo.x.toFixed(2)} ${eo.y.toFixed(2)}`,
    `L ${si.x.toFixed(2)} ${si.y.toFixed(2)}`,
    `A ${innerR} ${innerR} 0 ${largeArc} 0 ${ei.x.toFixed(2)} ${ei.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

/**
 * AC6 — buduje modele wykresów (bar/line/donut) jako czyste dane dla
 * szablonów SVG. Bez zewnętrznych bibliotek (Chart.js niedostępny w
 * zależnościach projektu) — natywne SVG z <pattern> daje pattern fills
 * wymagane przez WCAG wprost.
 */
@Injectable({ providedIn: "root" })
export class ChartRenderingService {
  /** Poziomy wykres słupkowy (np. compliance per moduł), skala 0..max. */
  buildBarChart(
    items: { label: string; value: number; colorClass?: string }[],
    options: { width?: number; barHeight?: number; gap?: number; max?: number } = {},
  ): BarChartModel {
    const width = options.width ?? 560;
    const barHeight = options.barHeight ?? 22;
    const gap = options.gap ?? 10;
    const max = options.max ?? Math.max(1, ...items.map((i) => i.value));

    const bars: BarChartBar[] = items.map((item, i) => ({
      label: item.label,
      value: item.value,
      x: 0,
      y: i * (barHeight + gap),
      width: Math.max(2, (Math.min(item.value, max) / max) * width),
      height: barHeight,
      patternId: PATTERN_IDS[i % PATTERN_IDS.length],
      colorClass: item.colorClass ?? `chart-color-${i % PATTERN_IDS.length}`,
    }));

    return {
      width,
      height: items.length * (barHeight + gap),
      bars,
    };
  }

  /** Wykres liniowy trendu (0-100). */
  buildLineChart(
    values: { label: string; value: number }[],
    options: { width?: number; height?: number; max?: number } = {},
  ): LineChartModel {
    const width = options.width ?? 560;
    const height = options.height ?? 200;
    const max = options.max ?? 100;
    const padding = 8;

    const innerW = width - padding * 2;
    const innerH = height - padding * 2;
    const n = values.length;

    const points: LineChartPoint[] = values.map((v, i) => ({
      label: v.label,
      value: v.value,
      x: padding + (n > 1 ? (i / (n - 1)) * innerW : innerW / 2),
      y: padding + innerH - (Math.min(v.value, max) / max) * innerH,
    }));

    const path = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
      .join(" ");
    const areaPath =
      points.length > 1
        ? `${path} L ${points[points.length - 1].x.toFixed(2)} ${height - padding} ` +
          `L ${points[0].x.toFixed(2)} ${height - padding} Z`
        : "";

    const gridLines = [0, 25, 50, 75, 100].map((value) => ({
      value,
      y: padding + innerH - (value / max) * innerH,
    }));

    return { width, height, path, areaPath, points, gridLines };
  }

  /** Wykres donut (np. rozkład severity). Pomija segmenty zerowe. */
  buildDonutChart(
    segments: { label: string; value: number; colorClass?: string }[],
    options: { size?: number; thickness?: number } = {},
  ): DonutChartModel {
    const size = options.size ?? 180;
    const thickness = options.thickness ?? 28;
    const cx = size / 2;
    const outerR = size / 2 - 2;
    const innerR = outerR - thickness;

    const nonZero = segments.filter((s) => s.value > 0);
    const total = nonZero.reduce((sum, s) => sum + s.value, 0);
    if (total === 0) {
      return { size, segments: [], total: 0 };
    }

    let angle = 0;
    const result: DonutSegment[] = nonZero.map((seg, i) => {
      const sweep = (seg.value / total) * 360;
      // Pełne koło (jeden segment) — SVG arc nie renderuje 360°.
      const end = Math.min(angle + sweep, angle + 359.98);
      const path = donutSegmentPath(cx, cx, outerR, innerR, angle, end);
      angle += sweep;
      const originalIndex = segments.indexOf(seg);
      return {
        label: seg.label,
        value: seg.value,
        percentage: Math.round((seg.value / total) * 100),
        path,
        patternId: PATTERN_IDS[originalIndex % PATTERN_IDS.length],
        colorClass:
          seg.colorClass ?? `chart-color-${originalIndex % PATTERN_IDS.length}`,
      };
    });

    return { size, segments: result, total };
  }
}
