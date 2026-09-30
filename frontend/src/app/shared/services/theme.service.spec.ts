import { TestBed } from "@angular/core/testing";
import {
  HIGH_CONTRAST_CLASS,
  HIGH_CONTRAST_STORAGE_KEY,
  REDUCED_MOTION_CLASS,
  REDUCED_MOTION_STORAGE_KEY,
  ThemeService,
} from "./theme.service";

describe("ThemeService", () => {
  let service: ThemeService;

  beforeEach(() => {
    localStorage.removeItem(HIGH_CONTRAST_STORAGE_KEY);
    localStorage.removeItem(REDUCED_MOTION_STORAGE_KEY);
    document.body.classList.remove(HIGH_CONTRAST_CLASS, REDUCED_MOTION_CLASS);
    TestBed.configureTestingModule({});
    service = TestBed.inject(ThemeService);
  });

  it("toggleHighContrast włącza klasę na body i zapisuje preferencję (AC6)", () => {
    service.toggleHighContrast();
    expect(service.isHighContrastSignal()).toBe(true);
    expect(document.body.classList.contains(HIGH_CONTRAST_CLASS)).toBe(true);
    expect(localStorage.getItem(HIGH_CONTRAST_STORAGE_KEY)).toBe("true");

    service.toggleHighContrast();
    expect(service.isHighContrastSignal()).toBe(false);
    expect(document.body.classList.contains(HIGH_CONTRAST_CLASS)).toBe(false);
    expect(localStorage.getItem(HIGH_CONTRAST_STORAGE_KEY)).toBe("false");
  });

  it("toggleReducedMotion włącza klasę na body i zapisuje preferencję (AC7)", () => {
    service.toggleReducedMotion();
    expect(service.isReducedMotionSignal()).toBe(true);
    expect(document.body.classList.contains(REDUCED_MOTION_CLASS)).toBe(true);
    expect(localStorage.getItem(REDUCED_MOTION_STORAGE_KEY)).toBe("true");
  });

  it("initialize odtwarza preferencje z localStorage (AC6/AC7)", () => {
    localStorage.setItem(HIGH_CONTRAST_STORAGE_KEY, "true");
    localStorage.setItem(REDUCED_MOTION_STORAGE_KEY, "true");
    service.initialize();
    expect(service.isHighContrastSignal()).toBe(true);
    expect(service.isReducedMotionSignal()).toBe(true);
    expect(document.body.classList.contains(HIGH_CONTRAST_CLASS)).toBe(true);
    expect(document.body.classList.contains(REDUCED_MOTION_CLASS)).toBe(true);
  });

  it("initialize aktywuje tryby z preferencji systemowych, gdy brak zapisu (AC2/AC4)", () => {
    vi.spyOn(window, "matchMedia").mockImplementation(
      (query: string) =>
        ({
          matches:
            query.includes("prefers-contrast") ||
            query.includes("prefers-reduced-motion"),
          addEventListener: () => undefined,
        }) as unknown as MediaQueryList,
    );
    service.initialize();
    expect(service.isHighContrastSignal()).toBe(true);
    expect(service.isReducedMotionSignal()).toBe(true);
  });

  it("jawny wybór użytkownika ma priorytet nad preferencją systemową", () => {
    localStorage.setItem(HIGH_CONTRAST_STORAGE_KEY, "false");
    vi.spyOn(window, "matchMedia").mockImplementation(
      (query: string) =>
        ({
          matches: query.includes("prefers-contrast"),
          addEventListener: () => undefined,
        }) as unknown as MediaQueryList,
    );
    service.initialize();
    expect(service.isHighContrastSignal()).toBe(false);
  });

  it("detectSystemPreferences zwraca false, gdy media queries nie pasują", () => {
    vi.spyOn(window, "matchMedia").mockImplementation(
      () =>
        ({
          matches: false,
          addEventListener: () => undefined,
        }) as unknown as MediaQueryList,
    );
    expect(service.detectSystemPreferences()).toEqual({
      highContrast: false,
      reducedMotion: false,
    });
  });
});
