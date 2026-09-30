import { ChartRenderingService, PATTERN_IDS } from "./chart-rendering.service";

describe("ChartRenderingService", () => {
  let service: ChartRenderingService;

  beforeEach(() => {
    service = new ChartRenderingService();
  });

  describe("buildBarChart", () => {
    it("scales bars to max and assigns pattern ids cyclically (AC6)", () => {
      const model = service.buildBarChart(
        [
          { label: "a", value: 100 },
          { label: "b", value: 50 },
        ],
        { width: 200, max: 100 },
      );
      expect(model.bars.length).toBe(2);
      expect(model.bars[0].width).toBe(200);
      expect(model.bars[1].width).toBe(100);
      expect(model.bars[0].patternId).toBe(PATTERN_IDS[0]);
      expect(model.bars[1].patternId).toBe(PATTERN_IDS[1]);
    });

    it("keeps a minimal visible width for zero values", () => {
      const model = service.buildBarChart([{ label: "a", value: 0 }], {
        max: 100,
      });
      expect(model.bars[0].width).toBe(2);
    });
  });

  describe("buildLineChart", () => {
    it("builds path, area and grid lines", () => {
      const model = service.buildLineChart([
        { label: "p1", value: 0 },
        { label: "p2", value: 100 },
      ]);
      expect(model.path.startsWith("M ")).toBe(true);
      expect(model.path).toContain("L ");
      expect(model.areaPath.endsWith("Z")).toBe(true);
      expect(model.points.length).toBe(2);
      expect(model.gridLines.map((g) => g.value)).toEqual([
        0, 25, 50, 75, 100,
      ]);
    });

    it("returns empty area path for a single point", () => {
      const model = service.buildLineChart([{ label: "p1", value: 50 }]);
      expect(model.areaPath).toBe("");
      expect(model.points.length).toBe(1);
    });
  });

  describe("buildDonutChart", () => {
    it("skips zero segments and computes percentages", () => {
      const model = service.buildDonutChart([
        { label: "krytyczne", value: 3 },
        { label: "wysokie", value: 0 },
        { label: "niskie", value: 1 },
      ]);
      expect(model.total).toBe(4);
      expect(model.segments.length).toBe(2);
      expect(model.segments[0].percentage).toBe(75);
      // Wzorek wg indeksu oryginalnego (AC6 — spójność legendy).
      expect(model.segments[1].patternId).toBe(PATTERN_IDS[2]);
    });

    it("returns empty model when all values are zero", () => {
      const model = service.buildDonutChart([{ label: "a", value: 0 }]);
      expect(model.total).toBe(0);
      expect(model.segments).toEqual([]);
    });

    it("renders a full circle as a single near-360 segment", () => {
      const model = service.buildDonutChart([{ label: "a", value: 5 }]);
      expect(model.segments.length).toBe(1);
      expect(model.segments[0].path).toContain("A ");
      expect(model.segments[0].percentage).toBe(100);
    });
  });
});
