# Moduły analizy — indeks

> Dokumentacja modułów generujących przypadki testowe i wyniki analiz.

## Przegląd

- [ai-modules.md](ai-modules.md) — **kompletna dokumentacja modułów AI (M1-M6):** dual-path engine, prompty LLM, benchmarki, golden data, porównanie native vs LLM vs hybrid, koszty, optymalizacja

## Analiza kodu źródłowego (Epic 1)

[analiza-kodu/](analiza-kodu/) — [ast-analysis](analiza-kodu/ast-analysis.md)
(parsowanie AST 11+ językami, tree-sitter) ·
[generowanie przypadków testowych](analiza-kodu/test-case-generation-native.md) ·
[generowanie kodu testów E2E](analiza-kodu/test-code-generation.md)
(Playwright/Cypress/Selenium) · [analiza regresji](analiza-kodu/regression-analysis.md) ·
[benchmarki i golden data](analiza-kodu/benchmarks.md)

## Analiza dokumentacji (Epic 2)

[analiza-dokumentacji/](analiza-dokumentacji/) —
[analiza dokumentów](analiza-dokumentacji/document-analysis.md)
(segmentacja, wymagania, glosariusz, niespójności; PDF/DOCX/OCR) ·
[formaty wejściowe](analiza-dokumentacji/document-formats.md)

## Analiza UML i GUI (Epic 3)

[analiza-uml-gui/](analiza-uml-gui/) —
[parsowanie UML](analiza-uml-gui/uml-parsing.md) (PlantUML/XMI/SVG+OCR) ·
[analiza GUI](analiza-uml-gui/gui-analysis.md) (zrzuty, detekcja komponentów) ·
[generowanie testów](analiza-uml-gui/test-generation-uml-gui.md) ·
[traceability](analiza-uml-gui/traceability-uml-gui.md) ·
[modele danych](analiza-uml-gui/uml-gui-data-models.md)

## Analiza bezpieczeństwa (Epic 4)

[bezpieczenstwo/](bezpieczenstwo/) — architektura modułu
([overview](bezpieczenstwo/01-architektura/01-overview.md): SAST, taint,
zależności, konfiguracja, DAST, agregator ryzyka) ·
[katalog reguł](bezpieczenstwo/02-katalog-regul/07-macierz-jezykow.md)
(SQLi, XSS, CSRF, authz, walidacja, sekrety, taint) ·
[pipeline DAST](bezpieczenstwo/03-pipeline-dast/01-integracja-zap.md) (ZAP,
payloady, autentykacja) · [pipeline CVE](bezpieczenstwo/04-pipeline-cve/01-zrodla-danych.md)
(źródła, harmonogram, auto-reguły, rescan)

Poradnik użytkownika modułu → [../user-guide/bezpieczenstwo/](../user-guide/bezpieczenstwo/)

## Analiza luk funkcjonalnych (Epic 5)

[luki-funkcjonalne/](luki-funkcjonalne/01-architektura/) —
[overview](luki-funkcjonalne/01-architektura/01-overview.md):
comparator (dopasowanie wymagań↔kod), klasyfikator 4 typów luk,
compliance scoring, rekomendacje, skeleton generator, integracje
(Jira/Azure DevOps), modele danych

Poradnik użytkownika modułu → [../user-guide/luki-funkcjonalne/](../user-guide/luki-funkcjonalne/)

## Granice modułów

- Analiza kodu (E1) dostarcza struktury logiczne wykorzystywane przez
  porównanie kod↔dokumentacja (E5) i traceability (E3).
- Analiza dokumentacji (E2) wyciąga wymagania — wejście modułu luk (E5).
- Bezpieczeństwo (E4) ma własne tabele wyników (`security_findings`),
  niezależne od `gap_findings` (E5).
