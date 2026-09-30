import { Injectable, signal } from "@angular/core";

/** Klucze localStorage z preferencjami dostępności (Story 6.10, AC6/AC7). */
export const HIGH_CONTRAST_STORAGE_KEY = "testgen:a11y:high-contrast";
export const REDUCED_MOTION_STORAGE_KEY = "testgen:a11y:reduced-motion";

/** Klasy CSS przełączane na <body>. */
export const HIGH_CONTRAST_CLASS = "high-contrast";
export const REDUCED_MOTION_CLASS = "reduced-motion";

/**
 * Story 6.10 — zarządzanie motywami dostępności:
 * - tryb wysokiego kontrastu (AC1/AC2/AC6): klasa `high-contrast` na body,
 * - redukcja animacji (AC4/AC7): klasa `reduced-motion` na body.
 *
 * Priorytet preferencji: localStorage (jawny wybór użytkownika)
 * > preferencje systemowe (`prefers-contrast: more`,
 * `prefers-reduced-motion: reduce`) > wyłączone.
 */
@Injectable({ providedIn: "root" })
export class ThemeService {
  readonly isHighContrastSignal = signal(false);
  readonly isReducedMotionSignal = signal(false);

  /** Inicjalizacja z localStorage + preferencji systemowych (raz na start). */
  initialize(): void {
    const storedContrast = this.readStored(HIGH_CONTRAST_STORAGE_KEY);
    const storedMotion = this.readStored(REDUCED_MOTION_STORAGE_KEY);
    const system = this.detectSystemPreferences();

    this.setHighContrast(storedContrast ?? system.highContrast);
    this.setReducedMotion(storedMotion ?? system.reducedMotion);

    // Reaguj na zmianę preferencji systemowych w trakcie sesji —
    // tylko gdy użytkownik nie dokonał jawnego wyboru w toolbarze.
    this.watchMedia("(prefers-contrast: more)", (matches) => {
      if (this.readStored(HIGH_CONTRAST_STORAGE_KEY) === null) {
        this.setHighContrast(matches);
      }
    });
    this.watchMedia("(prefers-reduced-motion: reduce)", (matches) => {
      if (this.readStored(REDUCED_MOTION_STORAGE_KEY) === null) {
        this.setReducedMotion(matches);
      }
    });
  }

  /** AC2/AC4 — detekcja preferencji systemowych przez matchMedia. */
  detectSystemPreferences(): { highContrast: boolean; reducedMotion: boolean } {
    return {
      highContrast: this.matches("(prefers-contrast: more)"),
      reducedMotion: this.matches("(prefers-reduced-motion: reduce)"),
    };
  }

  /** AC6 — przełącznik trybu wysokiego kontrastu (zapis w localStorage). */
  toggleHighContrast(): void {
    const next = !this.isHighContrastSignal();
    this.setHighContrast(next);
    this.writeStored(HIGH_CONTRAST_STORAGE_KEY, next);
  }

  /** AC7 — przełącznik redukcji animacji (zapis w localStorage). */
  toggleReducedMotion(): void {
    const next = !this.isReducedMotionSignal();
    this.setReducedMotion(next);
    this.writeStored(REDUCED_MOTION_STORAGE_KEY, next);
  }

  private setHighContrast(enabled: boolean): void {
    this.isHighContrastSignal.set(enabled);
    document.body.classList.toggle(HIGH_CONTRAST_CLASS, enabled);
  }

  private setReducedMotion(enabled: boolean): void {
    this.isReducedMotionSignal.set(enabled);
    document.body.classList.toggle(REDUCED_MOTION_CLASS, enabled);
  }

  private matches(query: string): boolean {
    return typeof window.matchMedia === "function"
      ? window.matchMedia(query).matches
      : false;
  }

  private watchMedia(
    query: string,
    onChange: (matches: boolean) => void,
  ): void {
    if (typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia(query);
    // addEventListener wspierany we wszystkich targetowanych przeglądarkach.
    mql.addEventListener?.("change", (event) => onChange(event.matches));
  }

  private readStored(key: string): boolean | null {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? null : raw === "true";
    } catch {
      return null;
    }
  }

  private writeStored(key: string, value: boolean): void {
    try {
      localStorage.setItem(key, String(value));
    } catch {
      // localStorage niedostępny (tryb prywatny) — preferencja tylko w pamięci.
    }
  }
}
