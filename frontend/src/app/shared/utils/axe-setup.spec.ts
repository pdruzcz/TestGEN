import {
  AXE_BLOCKING_IMPACTS,
  AXE_WCAG_TAGS,
  AxeViolationLike,
  blockingViolations,
  formatViolations,
} from "./axe-setup";

const violation = (
  impact: string | null,
  id = "color-contrast",
): AxeViolationLike => ({
  id,
  impact,
  help: "Elements must meet minimum color contrast ratio thresholds",
  helpUrl: "https://dequeuniversity.com/rules/axe/4.10/color-contrast",
  nodes: [{ html: "<p>tekst</p>", target: ["p.low-contrast"] }],
});

describe("axe-setup (AC7)", () => {
  it("konfiguracja obejmuje tagi WCAG 2.1 AA", () => {
    expect(AXE_WCAG_TAGS).toContain("wcag21aa");
    expect(AXE_WCAG_TAGS).toContain("wcag2aa");
  });

  it("blokujące poziomy to critical i serious", () => {
    expect([...AXE_BLOCKING_IMPACTS]).toEqual(["critical", "serious"]);
  });

  it("blockingViolations filtruje tylko critical/serious", () => {
    const result = blockingViolations([
      violation("critical"),
      violation("serious", "label"),
      violation("moderate", "region"),
      violation("minor", "landmark-one-main"),
      violation(null, "unknown"),
    ]);
    expect(result.length).toBe(2);
    expect(result.map((v) => v.id)).toEqual(["color-contrast", "label"]);
  });

  it("formatViolations zwraca czytelny raport z selektorami", () => {
    const report = formatViolations([violation("critical")]);
    expect(report).toContain("[critical] color-contrast");
    expect(report).toContain("p.low-contrast");
    expect(report).toContain("dequeuniversity.com");
  });

  it("formatViolations dla pustej listy potwierdza brak naruszeń", () => {
    expect(formatViolations([])).toContain("Brak naruszeń");
  });
});
