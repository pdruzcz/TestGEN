import {
  LOCATOR_STRATEGY_LABEL,
  detectLocatorStrategy,
  isUiFramework,
} from "./locator-strategy";

describe("locator-strategy", () => {
  describe("isUiFramework()", () => {
    it("recognises UI frameworks case-insensitively", () => {
      expect(isUiFramework("PLAYWRIGHT")).toBe(true);
      expect(isUiFramework("selenium")).toBe(true);
      expect(isUiFramework("CYPRESS")).toBe(true);
      expect(isUiFramework("Appium")).toBe(true);
    });

    it("rejects non-UI frameworks and empty input", () => {
      expect(isUiFramework("PYTEST")).toBe(false);
      expect(isUiFramework(null)).toBe(false);
      expect(isUiFramework(undefined)).toBe(false);
    });
  });

  describe("detectLocatorStrategy()", () => {
    it("detects data-testid at the top of the ladder", () => {
      expect(detectLocatorStrategy("page.getByTestId('login-submit')")).toBe(
        "data-testid",
      );
      expect(detectLocatorStrategy('<button data-testid="x">')).toBe(
        "data-testid",
      );
    });

    it("detects role+name", () => {
      expect(
        detectLocatorStrategy("page.getByRole('button', { name: 'OK' })"),
      ).toBe("role+name");
    });

    it("detects aria-label", () => {
      expect(detectLocatorStrategy("page.getByLabel('E-mail')")).toBe(
        "aria-label",
      );
    });

    it("detects id (Selenium Java By.id)", () => {
      expect(detectLocatorStrategy("driver.findElement(By.id('login'))")).toBe(
        "id",
      );
    });

    it("falls back to css for generic selectors", () => {
      expect(detectLocatorStrategy("page.querySelector('.btn-save')")).toBe(
        "css",
      );
    });

    it("returns null when no locator is present", () => {
      expect(detectLocatorStrategy("assert x == 1")).toBeNull();
      expect(detectLocatorStrategy(null)).toBeNull();
      expect(detectLocatorStrategy("")).toBeNull();
    });

    it("prefers data-testid over lower-rung matches", () => {
      const code = "page.getByTestId('save')\npage.getByRole('button')";
      expect(detectLocatorStrategy(code)).toBe("data-testid");
    });
  });

  it("labels every strategy in Polish", () => {
    expect(LOCATOR_STRATEGY_LABEL["role+name"]).toBe("rola + nazwa");
    expect(LOCATOR_STRATEGY_LABEL["css"]).toBe("CSS");
    expect(LOCATOR_STRATEGY_LABEL["data-testid"]).toBe("data-testid");
  });
});
