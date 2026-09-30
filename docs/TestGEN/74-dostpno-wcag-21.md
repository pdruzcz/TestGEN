# **7.4.** Dostępność (WCAG 2.1)

### **7.4.1.** Poziom zgodności

**REQ-A11Y-001:** Interfejs użytkownika musi być zgodny z WCAG 2.1
poziom AA.

### **7.4.2.** Szczegółowe wymagania WCAG

  ------------------------------------------------------------------------------
  **Kryterium WCAG**   **Poziom**   **Wymaganie**           **Implementacja**
  -------------------- ------------ ----------------------- --------------------
  1.1.1 Treść          A            Wszystkie obrazy muszą  Automatyczna
  nietekstowa                       mieć alt text           walidacja w CI

  1.3.1 Informacje i   A            Semantyczny HTML, ARIA  React components z
  relacje                           labels                  wbudowanym ARIA

  1.4.3 Kontrast       AA           Kontrast min. 4.5:1     Color system z
  (minimum)                         (tekst normalny), 3:1   automatyczną
                                    (duży tekst)            walidacją

  1.4.4 Zmiana         AA           Możliwość powiększenia  Responsywna
  rozmiaru tekstu                   do 200%                 typografia (rem
                                                            units)

  1.4.11 Kontrast      AA           Kontrast min. 3:1 dla   Dedykowany color
  elementów                         UI components           palette
  nietekstowych                                             

  2.1.1 Klawiatura     A            Pełna obsługa           Tab navigation,
                                    klawiatury              keyboard shortcuts

  2.1.2 Brak pułapki   A            Możliwość opuszczenia   Focus management
  klawiatury                        każdego elementu        

  2.4.3 Kolejność      A            Logiczna kolejność      Careful DOM
  fokusa                            tabulacji               structure

  2.4.7 Widoczny fokus AA           Wyraźny wskaźnik fokusa Custom focus styles
                                                            (outline, ring)

  3.1.1 Język strony   A            Określenie języka       lang=\"pl\"
                                    dokumentu               attribute

  3.2.3 Spójna         AA           Konsystentna struktura  Shared layout
  nawigacja                         nawigacji               components

  4.1.2 Nazwa, rola,   A            Prawidłowe ARIA         Automated
  wartość                           attributes              accessibility
                                                            testing
  ------------------------------------------------------------------------------

### **7.4.3.** Narzędzia do testowania dostępności

**Wykorzystywane narzędzia:**

- **axe-core** - Automatyczne testy dostępności w CI/CD

- **WAVE** - Browser extension do manualnej weryfikacji

- **Lighthouse** - Audyty dostępności w Chrome DevTools

- **NVDA / JAWS** - Testy z czytnikami ekranu

- **Keyboard navigation testing** - Manualne testy nawigacji

### **7.4.4.** Dodatkowe funkcje dostępności

- **Tryb wysokiego kontrastu** - Dedykowany motyw dla użytkowników
  słabowidzących

- **Powiększanie czcionki** - Kontrolki do zmiany rozmiaru tekstu (Small
  / Medium / Large / Extra Large)

- **Skip links** - Linki \"Przejdź do treści\" na początku strony

- **Keyboard shortcuts** - Skróty klawiszowe do najważniejszych funkcji

- **Screen reader announcements** - Live regions (aria-live) dla
  dynamicznych zmian

- **Reduced motion** - Respektowanie preferencji prefers-reduced-motion
