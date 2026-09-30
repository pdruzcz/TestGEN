/**
 * Locator-strategy detection for UI test cases — Story 1.51-zakańczenie (FR69).
 *
 * TestCase carries no explicit locator field; UI tests (Selenium/Playwright/
 * Cypress) embed locators in their ``testCode``. This pure helper infers the
 * primary locator strategy from the code so test-case management (Story 6.5)
 * can surface a badge matching the self-healing locator ladder
 * (data-testid > role+name > aria-label > id > CSS).
 */

export type LocatorStrategy =
  | "data-testid"
  | "role+name"
  | "aria-label"
  | "id"
  | "css";

const UI_FRAMEWORKS = new Set(["SELENIUM", "PLAYWRIGHT", "CYPRESS", "APPIUM"]);

/** Ordered by the self-healing locator ladder (most stable first). */
const STRATEGY_PATTERNS: ReadonlyArray<[LocatorStrategy, RegExp]> = [
  ["data-testid", /(?:getByTestId|data-testid\s*=)/i],
  ["role+name", /(?:getByRole\s*\(|role\s*=)/i],
  ["aria-label", /(?:getByLabel\s*\(|aria-label\s*=)/i],
  [
    "id",
    /(?:getElementById|By\.id\s*\(|ById\s*\(|querySelector\(\s*['"]#|#\w)/,
  ],
];

export function isUiFramework(framework: string | null | undefined): boolean {
  return !!framework && UI_FRAMEWORKS.has(framework.toUpperCase());
}

/**
 * Infer the primary locator strategy from a test's code, or ``null`` when no
 * recognised locator (or no code) is present.
 */
export function detectLocatorStrategy(
  testCode: string | null | undefined,
): LocatorStrategy | null {
  if (!testCode) return null;
  for (const [strategy, pattern] of STRATEGY_PATTERNS) {
    if (pattern.test(testCode)) return strategy;
  }
  // A UI test with selectors but no recognised stable strategy falls back to CSS.
  return /(?:querySelector|findElement|css\(|locator\()/i.test(testCode)
    ? "css"
    : null;
}

export const LOCATOR_STRATEGY_LABEL: Record<LocatorStrategy, string> = {
  "data-testid": "data-testid",
  "role+name": "rola + nazwa",
  "aria-label": "aria-label",
  id: "id",
  css: "CSS",
};
