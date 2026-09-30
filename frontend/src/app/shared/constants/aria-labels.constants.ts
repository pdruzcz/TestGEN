/**
 * Story 6.11, AC4 — wspólne polskie etykiety ARIA dla ikon i przycisków
 * bez tekstu wizualnego. Jedno źródło prawdy — spójne komunikaty
 * dla screen readerów w całej aplikacji.
 */
export const ARIA_LABELS = {
  close: "Zamknij",
  delete: "Usuń",
  deleteFile: "Usuń plik",
  edit: "Edytuj",
  download: "Pobierz",
  upload: "Prześlij plik",
  filter: "Filtruj",
  sort: "Sortuj",
  search: "Szukaj",
  refresh: "Odśwież",
  expand: "Rozwiń",
  collapse: "Zwiń",
  showPassword: "Pokaż hasło",
  hidePassword: "Ukryj hasło",
  previousPage: "Poprzednia strona",
  nextPage: "Następna strona",
  openMenu: "Otwórz menu",
  logout: "Wyloguj się",
  loading: "Ładowanie",
  progress: "Postęp operacji",
  mainNavigation: "Menu główne",
  skipToContent: "Przejdź do treści głównej",
} as const;

export type AriaLabelKey = keyof typeof ARIA_LABELS;
