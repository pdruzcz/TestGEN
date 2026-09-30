# Inwentaryzacja dokumentacji fazowej — Story 9.1 (Task 1)

> Arkusz inwentaryzacji źródeł konsolidacji. Stan: baseline `5f0ae63` (2026-09-15).
> Metryki: liczba linii + data ostatniego commitu dot. pliku.
> Jakość (wstępna): **w** = wysoka (aktualna, uziemiona w kodzie), **ś** = średnia
> (kompletna, starsza lub wymagująca de-dualizacji), **i** = indeks/spis (niska
> informacyjność samodzielna, treść wchłaniana do README).

## Zakres i decyzje ramowe (zatwierdzone przez Ownera)

1. Konsolidujemy to, co istnieje: `docs/p1/`, `docs/p2/`, `docs/test-env/`.
   Katalogi `docs/p3/`, `docs/api/`, `docs/security/` z założeń story **nie
   istnieją** (treść API/security jest już w p1/p2). Dokumentacja Epic 8
   (story 8-5/8-13, w toku) trafi od razu do `docs/final/`.
2. Katalogi fazowe `docs/p1/`, `docs/p2/`, `docs/test-env/` **znikają** po
   przeniesieniu treści (bez duplikacji — AC3).
3. `docs/TestGEN/` (oryginalna specyfikacja produktu, 40 plików) — **poza
   zakresem**, nietknięte (punkt odniesienia, nie dokumentacja fazowa).
4. **De-dualizacja**: przy scalaniu usuwamy sekcje LLM/hybrid/dual-path
   (zasada native-only od konsolidacji E3 wzwyż). Dotyczy: E4 `08-dual-path.md`,
   E5 `07-dual-path.md` + wzmianki w treści.
5. `docs/sample-srs.md` — przykład/szablon bez referencji w kodzie — **poza
   zakresem** (zostaje w `docs/`).

Legenda decyzji: **MOVE** = git mv do celu (historia zachowana),
**FOLD** = treść wchłaniana do dokumentu docelowego, źródło usuwane,
**DELETE** = usuwany bez przenoszenia (de-dualizacja),
**KEEP** = bez zmian.

## 1. docs/p1/ — faza P1 (Epic 1–3, model 1.50) — 41 plików

### Poziom korzenia (6)

| Plik | Temat | Epik | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|---|
| `README.md` | Indeks dokumentacji P1 + sekcje epików | E1–E3 | 81 | 2026-07-16 | i | FOLD → `final/README.md` + `final/architecture/README.md` |
| `architecture.md` | Architektura systemu (przegląd) | E1 | 104 | 2026-06-23 | w | MOVE → `final/architecture/system.md` |
| `conventions.md` | Konwencje repo/kodu/dokumentacji | E1 | 82 | 2026-06-23 | w | MOVE → `final/architecture/conventions.md` |
| `workflows.md` | Przepływy pracy (dev → review → release) | E1 | 71 | 2026-06-23 | w | MOVE → `final/architecture/workflows.md` |
| `environment-setup.md` | Środowisko produkcyjne (env, sekrety, serwisy) | E1 | 107 | 2026-07-09 | w | MOVE → `final/deployment-guide/environment-setup.md` |
| `getting-started.md` | Pierwsze uruchomienie (dev) | E1 | 119 | 2026-07-09 | w | MOVE → `final/deployment-guide/getting-started.md` |

### adr/ (14)

| Plik | Temat | Epik | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|---|
| `ADR-001-custom-monorepo.md` | Monorepo FastAPI+Angular+Flutter | E1 | 49 | 2026-07-09 | w | MOVE → `final/architecture/adr/` (nazwy bez zmian) |
| `ADR-002-multi-tenancy-rls.md` | Multi-tenancy + RLS | E1 | 44 | 2026-06-23 | w | MOVE → j.w. |
| `ADR-003-argon2id-rs256-jwt.md` | Argon2id + RS256 JWT | E1 | 48 | 2026-06-23 | w | MOVE → j.w. |
| `ADR-004-celery-rabbitmq.md` | Celery + RabbitMQ (+ Flower prod) | E1 | 58 | 2026-07-09 | w | MOVE → j.w. |
| `ADR-005-tree-sitter-parser.md` | Parser AST tree-sitter | E1 | 41 | 2026-06-23 | w | MOVE → j.w. |
| `ADR-006-jinja2-template-engine.md` | Szablony Jinja2 | E1 | 40 | 2026-06-23 | w | MOVE → j.w. |
| `ADR-007-e2e-frameworks.md` | Frameworki E2E | E1 | 44 | 2026-06-23 | w | MOVE → j.w. |
| `ADR-008-golden-data.md` | Golden data + accuracy gate | E1 | 45 | 2026-06-23 | w | MOVE → j.w. |
| `ADR-009-code-review-workflow.md` | Workflow review | E1 | 48 | 2026-06-23 | w | MOVE → j.w. |
| `ADR-010-audit-logging.md` | Audit log | E1 | 40 | 2026-06-23 | w | MOVE → j.w. |
| `ADR-011-uml-visual-tier2.md` | UML wizualny Tier 2 (OCR) | E3 | 56 | 2026-07-16 | w | MOVE → j.w. |
| `ADR-012-sikulix-image-based.md` | Testy obrazowe SikuliX | E3 | 56 | 2026-07-16 | w | MOVE → j.w. |
| `ADR-013-traceability-proxy.md` | Traceability proxy | E3 | 52 | 2026-07-16 | w | MOVE → j.w. |
| `TEMPLATE.md` | Szablon ADR | E1 | 27 | 2026-06-23 | ś | MOVE → j.w. |

### ai/ (13)

| Plik | Temat | Epik | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|---|
| `ast-analysis.md` | Analiza AST kodu | E1 | 58 | 2026-06-23 | w | MOVE → `final/ai-modules/analiza-kodu/` |
| `test-case-generation-native.md` | Generowanie TC (deterministyczne) | E1 | 45 | 2026-06-23 | w | MOVE → j.w. |
| `test-code-generation.md` | Generowanie kodu testów E2E | E1 | 49 | 2026-06-23 | w | MOVE → j.w. |
| `regression-analysis.md` | Analiza regresji | E1 | 34 | 2026-06-23 | w | MOVE → j.w. |
| `benchmarks.md` | Benchmarki + golden data | E1 | 75 | 2026-06-23 | w | MOVE → j.w. |
| `document-analysis.md` | Analiza dokumentacji | E2 | 120 | 2026-06-23 | w | MOVE → `final/ai-modules/analiza-dokumentacji/` |
| `document-formats.md` | Formaty dokumentów | E2 | 79 | 2026-07-16 | w | MOVE → j.w. |
| `uml-parsing.md` | Parsowanie UML | E3 | 98 | 2026-07-16 | w | MOVE → `final/ai-modules/analiza-uml-gui/` |
| `gui-analysis.md` | Analiza GUI (OCR/CV) | E3 | 119 | 2026-07-16 | w | MOVE → j.w. |
| `test-generation-uml-gui.md` | Generowanie testów z UML/GUI | E3 | 73 | 2026-07-16 | w | MOVE → j.w. |
| `traceability-uml-gui.md` | Traceability UML/GUI | E3 | 72 | 2026-07-16 | w | MOVE → j.w. |
| `uml-gui-data-models.md` | Modele danych UML/GUI | E3 | 204 | 2026-07-16 | w | MOVE → j.w. |

### api/ (8)

| Plik | Temat | Epik | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|---|
| `overview.md` | Przegląd API | E1 | 76 | 2026-06-23 | w | MOVE → `final/architecture/api/` |
| `examples/auth_examples.md` | Przykłady API auth | E1 | 96 | 2026-06-23 | w | MOVE → `final/architecture/api/examples/` |
| `examples/projects_examples.md` | Przykłady API projektów | E1 | 100 | 2026-06-23 | w | MOVE → j.w. |
| `examples/analysis_examples.md` | Przykłady API analiz | E1 | 83 | 2026-06-23 | w | MOVE → j.w. |
| `examples/test_cases_examples.md` | Przykłady API TC | E1 | 94 | 2026-06-23 | w | MOVE → j.w. |
| `examples/documents_examples.md` | Przykłady API dokumentacji | E2 | 122 | 2026-06-23 | w | MOVE → j.w. |
| `examples/uml_gui_examples.md` | Przykłady API UML/GUI | E3 | 133 | 2026-07-16 | w | MOVE → j.w. |
| `examples/audit_examples.md` | Przykłady API audytu | E1 | 64 | 2026-06-23 | w | MOVE → j.w. |

## 2. docs/p2/ — faza P2 (Epic 4–7) — 81 plików

### moduly-bezpieczenstwa/ (30, Epic 4)

| Plik | Temat | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|
| `00-spis-tresci.md` | Indeks modułu | 58 | 2026-06-12 | i | FOLD → `final/ai-modules/README.md` |
| `01-architektura/01-overview.md` | Przegląd modułu bezpieczeństwa | 110 | 2026-06-12 | ś | MOVE → `final/ai-modules/bezpieczenstwo/01-architektura/` (de-dual) |
| `01-architektura/02-sast-engine.md` | Silnik SAST | 86 | 2026-06-12 | ś | MOVE → j.w. |
| `01-architektura/03-taint-analyzer.md` | Analiza taint | 76 | 2026-06-12 | ś | MOVE → j.w. |
| `01-architektura/04-dependency-scanner.md` | Skaner zależności (CVE) | 77 | 2026-06-12 | ś | MOVE → j.w. |
| `01-architektura/05-config-scanner.md` | Skaner konfiguracji | 73 | 2026-06-12 | ś | MOVE → j.w. |
| `01-architektura/06-dast-runner.md` | Runner DAST (ZAP) | 61 | 2026-06-12 | ś | MOVE → j.w. |
| `01-architektura/07-agregator-i-risk-engine.md` | Agregator + risk scoring | 92 | 2026-06-12 | ś | MOVE → j.w. |
| `01-architektura/08-dual-path.md` | **Dual-path native/LLM** | 59 | 2026-06-12 | ś | **DELETE** (native-only) |
| `01-architektura/09-modele-danych.md` | Modele danych (ERD) | 76 | 2026-06-12 | ś | MOVE → j.w. (de-dual) |
| `02-katalog-regul/01..08` (8 pl.) | Katalog reguł: SQLi, XSS, CSRF, authz, input, secrets, macierz języków, taint-defs | 48–65 | 2026-06-12 | ś | MOVE → `final/ai-modules/bezpieczenstwo/02-katalog-regul/` |
| `03-pipeline-dast/01..04` (4 pl.) | Pipeline DAST: ZAP, payloady, auth, parsowanie | 43–53 | 2026-06-12 | ś | MOVE → `final/ai-modules/bezpieczenstwo/03-pipeline-dast/` |
| `04-pipeline-cve/01..04` (4 pl.) | Pipeline CVE: źródła, harmonogram, auto-reguły, rescan | 48–56 | 2026-06-12 | ś | MOVE → `final/ai-modules/bezpieczenstwo/04-pipeline-cve/` |
| `05-przewodnik-uzytkownika/01..05` (5 pl.) | Przewodnik: skan, wyniki, priorytety, rekomendacje, FAQ | 59–71 | 2026-06-12 | ś | MOVE → `final/user-guide/bezpieczenstwo/` (de-dual) |
| `05-przewodnik-uzytkownika/06-glosariusz.md` | Glosariusz bezpieczeństwa | 33 | 2026-06-12 | i | FOLD → `final/glosariusz.md` |

### modul-luk-funkcjonalnych/ (16, Epic 5)

| Plik | Temat | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|
| `00-spis-tresci.md` | Indeks modułu | 47 | 2026-07-20 | i | FOLD → `final/ai-modules/README.md` |
| `01-architektura/01-overview.md` | Przegląd modułu luk | 134 | 2026-07-20 | ś | MOVE → `final/ai-modules/luki-funkcjonalne/01-architektura/` (de-dual) |
| `01-architektura/02-comparator.md` | Dopasowanie wymagań↔kod | 141 | 2026-07-20 | ś | MOVE → j.w. (de-dual) |
| `01-architektura/03-klasyfikator-luk.md` | Klasyfikator 4 typów luk | 145 | 2026-07-20 | ś | MOVE → j.w. |
| `01-architektura/04-compliance-engine.md` | Compliance scoring | 114 | 2026-07-20 | ś | MOVE → j.w. |
| `01-architektura/05-recommendation-engine.md` | Rekomendacje | 125 | 2026-07-20 | ś | MOVE → j.w. (de-dual) |
| `01-architektura/06-skeleton-generator.md` | Skeleton code generator | 96 | 2026-07-20 | ś | MOVE → j.w. |
| `01-architektura/07-dual-path.md` | **Dual-path native/LLM** | 121 | 2026-08-24 | ś | **DELETE** (native-only) |
| `01-architektura/08-integracje.md` | Integracje Jira/ADO | 166 | 2026-07-20 | ś | MOVE → j.w. |
| `01-architektura/09-modele-danych.md` | Modele danych (ERD) | 141 | 2026-07-20 | ś | MOVE → j.w. (de-dual) |
| `02-przewodnik-uzytkownika/01..06` (6 pl.) | Przewodnik: uruchamianie, wyniki, compliance, rekomendacje, integracje, FAQ | 89–154 | 2026-07-20 | ś | MOVE → `final/user-guide/luki-funkcjonalne/` (de-dual) |
| `02-przewodnik-uzytkownika/07-glosariusz.md` | Glosariusz modułu (33 terminy) | 193 | 2026-07-20 | i | FOLD → `final/glosariusz.md` |

### interfejs-webowy/ (17, Epic 6)

| Plik | Temat | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|
| `00-spis-tresci.md` | Indeks modułu | 55 | 2026-09-15 | i | FOLD → `final/user-guide/README.md` + `final/architecture/README.md` |
| `01-architektura/01..08` (8 pl.) | Stack, struktura, ekrany, WCAG fundamenty/motywy/ARIA, Flutter, testy | 57–95 | 2026-09-15 | w | MOVE → `final/architecture/interfejs-webowy/` |
| `01-architektura/09-panel-administracyjny.md` | Panel admina (arch.) | 40 | 2026-09-15 | w | FOLD → `final/admin-guide/panel-administracyjny.md` (merge z przewodnikiem) |
| `02-przewodnik-uzytkownika/01..05` (5 pl.) | Nawigacja, projekty/upload, wyniki/TC, raporty, dostępność | 47–58 | 2026-09-15 | w | MOVE → `final/user-guide/interfejs-webowy/` |
| `02-przewodnik-uzytkownika/06-panel-admina.md` | Panel admina (przewodnik) | 52 | 2026-09-15 | w | FOLD → `final/admin-guide/panel-administracyjny.md` |
| `02-przewodnik-uzytkownika/07-glosariusz.md` | Glosariusz UI (29 terminów) | 34 | 2026-09-15 | i | FOLD → `final/glosariusz.md` |

### modul-billingu/ (18, Epic 7)

| Plik | Temat | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|
| `00-spis-tresci.md` | Indeks modułu | 63 | 2026-09-15 | i | FOLD → `final/user-guide/README.md` + `final/architecture/README.md` |
| `01-architektura/01..10` (10 pl.) | Przegląd, plany, tpay, webhooki, tokeny, proration, limity, powiadomienia/gating, faktury, ERD | 65–135 | 2026-09-15 | w | MOVE → `final/architecture/billing/` |
| `02-przewodnik-uzytkownika/01..06` (6 pl.) | Plany/zakup, subskrypcja, metody płatności, faktury, zużycie, FAQ | 41–78 | 2026-09-15 | w | MOVE → `final/user-guide/billing/` |
| `02-przewodnik-uzytkownika/07-glosariusz.md` | Glosariusz billing (28 terminów) | 33 | 2026-09-15 | i | FOLD → `final/glosariusz.md` |

## 3. docs/test-env/ (1)

| Plik | Temat | Epik | Linie | Aktualizacja | Jakość | Decyzja → Cel |
|---|---|---|---|---|---|---|
| `tpay-sandbox-runbook.md` | Runbook sandboxa tpay (14 scenariuszy) | E7 | 325 | 2026-09-11 | w | MOVE → `final/troubleshooting/tpay-sandbox-runbook.md` |

## 4. Poza zakresem konsolidacji

| Ścieżka | Uzasadnienie |
|---|---|
| `docs/TestGEN/` (40 pl.) | Oryginalna specyfikacja produktu — źródło odniesienia, nie dokumentacja fazowa |
| `docs/sample-srs.md` | Przykład SRS bez referencji w kodzie/testach |
| `backend/scripts/export_openapi.py` | Lokalne narzędzie dev (gitignored); wskazuje już nieistniejącą ścieżkę `docs/p1/modul-dokumentacji/` — do odświeżenia przy okazji E8 (8-13) |

## 5. Zidentyfikowane nakładające się tematy (AC2)

| Temat | Pliki źródłowe | Rozstrzygnięcie |
|---|---|---|
| Glosariusze (4× modułowe, łącznie ~120 terminów) | E4 `06-glosariusz`, E5 `07-glosariusz`, E6 `07-glosariusz`, E7 `07-glosariusz` | Jeden `final/glosariusz.md` (deduplikacja, alfabetycznie) |
| Panel administracyjny | E6 `01-architektura/09` + `02-przewodnik/06` | Merge → `final/admin-guide/panel-administracyjny.md` |
| Spisy treści modułów (4×) | `00-spis-tresci.md` E4/E5/E6/E7 | Wchłaniane do README sekcji final/ |
| Limity planów / gating (wzmianki w przewodnikach UI vs moduł billing) | E6 przewodnik ×4, E7 kompletnie | E7 pozostaje źródłem prawdy; E6 kieruje linkiem do `user-guide/billing/` + `architecture/billing/` |
| Tryby pracy silnika (dual-path) | E4 `08-dual-path.md`, E5 `07-dual-path.md` + wzmianki w overview/comparator/recommendation/modele/przewodnik | DELETE + de-dualizacja wzmianek (native-only) |
| Środowisko: env/sekrety | p1 `environment-setup.md` vs `getting-started.md` (rozjazd per plik nie występuje — komplementarne) | Rozdział zachowany (prod vs dev), oba → `deployment-guide/` |

## 6. Statystyki źródeł

| Źródło | Pliki | Linie | MOVE | FOLD | DELETE |
|---|---|---|---|---|---|
| docs/p1/ | 41 | 2 846 | 40 | 1 | 0 |
| docs/p2/ | 83 | 6 500 | 71 | 10 | 2 |
| docs/test-env/ | 1 | 325 | 1 | 0 | 0 |
| **Razem** | **125** | **9 671** | **112** | **11** | **2** |

Rozbieżność względem wstępnego szkicu (123): moduł bezpieczeństwa (E4)
liczy 32 pliki (wstępnie zliczono 30). Liczby zweryfikowane stanem gita
po konsolidacji: 112 rename (R100), 13 delete (11 FOLD + 2 DELETE),
9 nowych plików struktury.
