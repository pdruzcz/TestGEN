/**
 * Story 6.9, AC7 — wspólna konfiguracja axe-core dla testów dostępności
 * (unit i E2E). Zakres: WCAG 2.1 poziom AA.
 */

/** Tagi reguł axe-core odpowiadające WCAG 2.1 AA. */
export const AXE_WCAG_TAGS = [
  "wcag2a",
  "wcag2aa",
  "wcag21a",
  "wcag21aa",
] as const;

/** Poziomy naruszeń blokujące pipeline (AC7: 0 critical/serious). */
export const AXE_BLOCKING_IMPACTS = ["critical", "serious"] as const;

/** Opcje uruchomienia axe.run() — wspólne dla unit testów i CI. */
export const AXE_RUN_OPTIONS = {
  runOnly: {
    type: "tag" as const,
    values: [...AXE_WCAG_TAGS],
  },
  resultTypes: ["violations" as const],
};

interface AxeNodeLike {
  html: string;
  target: unknown[];
}

export interface AxeViolationLike {
  id: string;
  impact?: string | null;
  help: string;
  helpUrl: string;
  nodes: AxeNodeLike[];
}

/** Filtruje naruszenia do poziomów blokujących (critical/serious). */
export function blockingViolations(
  violations: AxeViolationLike[],
): AxeViolationLike[] {
  return violations.filter((violation) =>
    (AXE_BLOCKING_IMPACTS as readonly string[]).includes(
      violation.impact ?? "",
    ),
  );
}

/** Formatuje naruszenia do czytelnego raportu tekstowego (logi CI). */
export function formatViolations(violations: AxeViolationLike[]): string {
  if (violations.length === 0) {
    return "Brak naruszeń dostępności (WCAG 2.1 AA).";
  }
  return violations
    .map((violation) => {
      const nodes = violation.nodes
        .map((node) => `    - ${node.target.join(" ")}`)
        .join("\n");
      return [
        `[${violation.impact ?? "unknown"}] ${violation.id}: ${violation.help}`,
        `  ${violation.helpUrl}`,
        nodes,
      ].join("\n");
    })
    .join("\n\n");
}

/**
 * Uruchamia axe-core na elemencie DOM (użycie w testach jednostkowych).
 * Wymaga zainstalowanego pakietu `axe-core`.
 */
export async function runAxe(
  element: Element,
): Promise<AxeViolationLike[]> {
  const axe = await import("axe-core");
  const results = await axe.default.run(element, AXE_RUN_OPTIONS);
  return results.violations as unknown as AxeViolationLike[];
}
