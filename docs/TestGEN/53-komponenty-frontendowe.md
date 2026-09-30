# **5.3.** Komponenty frontendowe

### **5.3.1.** Web Application (React)

#### Architektura frontendowa

- **Framework:** React 18+ z TypeScript

- **State Management:** Redux Toolkit / Zustand

- **UI Library:** Material-UI (MUI) v5+

- **Routing:** React Router v6

- **API Client:** Axios / React Query

- **Build Tool:** Vite

#### Główne moduły UI

  -----------------------------------------------------------------------
  **Moduł**        **Funkcjonalność**      **Komponenty kluczowe**
  ---------------- ----------------------- ------------------------------
  Dashboard        Przegląd projektów,     ProjectList, StatsWidget,
                   statystyki              RecentActivity

  Code Upload      Wgrywanie kodu,         FileUploader,
                   konfiguracja analizy    LanguageSelector,
                                           AnalysisConfig

  Documentation    Wgrywanie dokumentacji  DocUploader, FormatSelector,
  Upload                                   PreviewPanel

  Analysis Results Wyniki analizy,         ResultsViewer,
                   wizualizacje            CodeHighlighter, DiffViewer

  Test Cases       Przeglądanie i edycja   TestCaseList, TestCaseEditor,
                   testów                  TestRunner

  Reports          Raporty, wykresy,       ReportGenerator,
                   eksport                 ChartComponents, ExportDialog
  -----------------------------------------------------------------------

#### Wymagania dostępności (WCAG 2.1)

**REQ-UI-001:** Wszystkie komponenty UI muszą być zgodne z WCAG 2.1
poziom AA.

Implementacja wymagań WCAG:

- **Kontrast kolorów:** Współczynnik minimum 4.5:1 dla tekstu
  normalnego, 3:1 dla dużego tekstu

- **Nawigacja klawiaturą:** Wszystkie funkcje dostępne bez myszy,
  widoczne fokus indicators

- **Atrybuty ARIA:** Wszystkie interaktywne elementy z odpowiednimi
  rolami, labels i states

- **Responsywność:** Działanie na urządzeniach od 320px do 4K

- **Skalowanie tekstu:** Możliwość powiększenia do 200% bez utraty
  funkcjonalności

- **Tryb wysokiego kontrastu:** Dedykowany motyw dla użytkowników
  słabowidzących

### **5.3.2.** Mobile Application (Flutter)

#### Architektura mobilna

- **Framework:** Flutter 3.x+

- **State Management:** Riverpod / BLoC

- **Local Storage:** Hive / SQLite

- **HTTP Client:** Dio

- **Platforms:** iOS 13+, Android 8+
