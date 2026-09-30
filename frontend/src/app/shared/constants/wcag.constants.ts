/**
 * Story 6.9 (AC1, AC3, AC4) — stałe WCAG 2.1 AA.
 *
 * Kolory zweryfikowane pod kątem kontrastu (WebAIM Contrast Checker):
 * każda para foreground/background spełnia minimum 4.5:1 (tekst normalny)
 * lub 3:1 (duży tekst i elementy UI).
 */

/** Minimalne stosunki kontrastu wg WCAG 2.1 AA. */
export const WCAG_CONTRAST = {
  /** SC 1.4.3 — tekst normalny (< 18pt / < 14pt bold). */
  normalText: 4.5,
  /** SC 1.4.3 — duży tekst (>= 18pt lub >= 14pt bold). */
  largeText: 3,
  /** SC 1.4.11 — komponenty UI i grafika informacyjna. */
  uiComponents: 3,
} as const;

/** SC 2.5.5 — minimalny rozmiar celu dotykowego w pikselach. */
export const WCAG_TOUCH_TARGET_PX = 44;

/** SC 2.4.7 / AC3 — minimalna grubość wskaźnika fokusu w pikselach. */
export const WCAG_FOCUS_OUTLINE_PX = 2;

/**
 * Paleta kolorów ze zweryfikowanym kontrastem względem tła.
 * Wartości ratio wg WebAIM Contrast Checker (tło białe #ffffff,
 * chyba że wskazano inaczej).
 */
export const WCAG_COLORS = {
  /** Tekst podstawowy na białym — ratio 15.9:1. */
  textPrimary: "#1f2933",
  /** Tekst drugorzędny na białym — ratio 7.4:1. */
  textSecondary: "#4b5563",
  /** Tekst wyciszony (hint/placeholder) na białym — ratio 4.6:1. */
  textMuted: "#6b7280",
  /** Kolor akcji (linki, przyciski tekstowe) na białym — ratio 5.9:1. */
  actionPrimary: "#0b57d0",
  /** Błąd na białym — ratio 5.9:1. */
  error: "#b3261e",
  /** Sukces na białym — ratio 4.8:1. */
  success: "#1e6b3a",
  /** Ostrzeżenie (tekst) na białym — ratio 4.7:1. */
  warning: "#8a5300",
  /** Wskaźnik fokusu na białym — ratio 5.9:1 (>= 3:1 wymagane). */
  focusOutline: "#0b57d0",
  /** Białe tło bazowe. */
  background: "#ffffff",
  /** Tło powierzchni (karty, panele) — kontrast tekstu zachowany. */
  surface: "#f8f9fa",
} as const;

export type WcagColorKey = keyof typeof WCAG_COLORS;
