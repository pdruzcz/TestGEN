# Raport konsolidacji dokumentacji — Story 9.1

> Konsolidacja dokumentacji fazowej P1–P2 do `docs/final/`.
> Baseline: `5f0ae63` (2026-09-15). Wykonanie: 112 rename (git mv, historia
> zachowana — `git log --follow`), 11 fold (treść wchłonięta, źródło usunięte),
> 2 delete (de-dualizacja). Razem przetworzone źródła: **125**.
> Kompletna decyzja per plik: [inwentaryzacja-dokumentacji.md](inwentaryzacja-dokumentacji.md).

## 1. Statystyki

| Miara | Wartość |
|---|---|
| Przetworzone źródła (p1 + p2 + test-env) | 125 |
| MOVE (git mv → final/, R100) | 112 |
| FOLD (treść scalona, plik usunięty) | 11 |
| DELETE (de-dualizacja, bez przenoszenia) | 2 |
| Nowe pliki struktury final/ | 10 (README ×7, glosariusz, raport, inwentaryzacja) + panel-administracyjny |
| Zerwane linki po konsolidacji | 0 (walidacja `scripts/validate_final_docs.py`) |

## 2. Mapa źródło → cel

### docs/p1/ (41 plików)

| Źródło | Cel | Status |
|---|---|---|
| `p1/README.md` | `final/README.md` + `final/architecture/README.md` | merged (fold) |
| `p1/architecture.md` | `final/architecture/system.md` | merged (move) |
| `p1/conventions.md` | `final/architecture/conventions.md` | merged (move; drzewo katalogów zaktualizowane) |
| `p1/workflows.md` | `final/architecture/workflows.md` | merged (move) |
| `p1/environment-setup.md` | `final/deployment-guide/environment-setup.md` | merged (move) |
| `p1/getting-started.md` | `final/deployment-guide/getting-started.md` | merged (move) |
| `p1/adr/` (ADR-001..013 + TEMPLATE, 14 pl.) | `final/architecture/adr/` | merged (move) |
| `p1/api/` (overview + examples ×7) | `final/architecture/api/` | merged (move) |
| `p1/ai/` (5 pl. E1) | `final/ai-modules/analiza-kodu/` | merged (move) |
| `p1/ai/` (2 pl. E2) | `final/ai-modules/analiza-dokumentacji/` | merged (move) |
| `p1/ai/` (5 pl. E3) | `final/ai-modules/analiza-uml-gui/` | merged (move) |

### docs/p2/ (83 pliki)

| Źródło | Cel | Status |
|---|---|---|
| `p2/moduly-bezpieczenstwa/00-spis-tresci.md` | `final/ai-modules/README.md` | merged (fold) |
| `p2/moduly-bezpieczenstwa/01-architektura/` (8 z 9 pl.) | `final/ai-modules/bezpieczenstwo/01-architektura/` | merged (move, de-dual) |
| `p2/moduly-bezpieczenstwa/01-architektura/08-dual-path.md` | — | **deleted** (native-only) |
| `p2/moduly-bezpieczenstwa/02-katalog-regul/` (8 pl.) | `final/ai-modules/bezpieczenstwo/02-katalog-regul/` | merged (move) |
| `p2/moduly-bezpieczenstwa/03-pipeline-dast/` (4 pl.) | `final/ai-modules/bezpieczenstwo/03-pipeline-dast/` | merged (move) |
| `p2/moduly-bezpieczenstwa/04-pipeline-cve/` (4 pl.) | `final/ai-modules/bezpieczenstwo/04-pipeline-cve/` | merged (move, de-dual) |
| `p2/moduly-bezpieczenstwa/05-przewodnik-uzytkownika/` (5 z 6 pl.) | `final/user-guide/bezpieczenstwo/` | merged (move, de-dual) |
| `p2/moduly-bezpieczenstwa/05-…/06-glosariusz.md` | `final/glosariusz.md` | merged (fold) |
| `p2/modul-luk-funkcjonalnych/00-spis-tresci.md` | `final/ai-modules/README.md` | merged (fold) |
| `p2/modul-luk-funkcjonalnych/01-architektura/` (8 z 9 pl.) | `final/ai-modules/luki-funkcjonalne/01-architektura/` | merged (move, de-dual) |
| `p2/modul-luk-funkcjonalnych/01-architektura/07-dual-path.md` | — | **deleted** (native-only) |
| `p2/modul-luk-funkcjonalnych/02-przewodnik-uzytkownika/` (6 z 7 pl.) | `final/user-guide/luki-funkcjonalne/` | merged (move, de-dual) |
| `p2/modul-luk-funkcjonalnych/02-…/07-glosariusz.md` | `final/glosariusz.md` | merged (fold) |
| `p2/interfejs-webowy/00-spis-tresci.md` | `final/user-guide/README.md` + `final/architecture/README.md` | merged (fold) |
| `p2/interfejs-webowy/01-architektura/` (8 z 9 pl.) | `final/architecture/interfejs-webowy/` | merged (move) |
| `p2/interfejs-webowy/01-…/09-panel-administracyjny.md` | `final/admin-guide/panel-administracyjny.md` | merged (fold, z przewodnikiem 06) |
| `p2/interfejs-webowy/02-przewodnik-uzytkownika/` (5 z 7 pl.) | `final/user-guide/interfejs-webowy/` | merged (move) |
| `p2/interfejs-webowy/02-…/06-panel-admina.md` | `final/admin-guide/panel-administracyjny.md` | merged (fold) |
| `p2/interfejs-webowy/02-…/07-glosariusz.md` | `final/glosariusz.md` | merged (fold) |
| `p2/modul-billingu/00-spis-tresci.md` | `final/user-guide/README.md` + `final/architecture/README.md` | merged (fold) |
| `p2/modul-billingu/01-architektura/` (10 pl.) | `final/architecture/billing/` | merged (move) |
| `p2/modul-billingu/02-przewodnik-uzytkownika/` (6 z 7 pl.) | `final/user-guide/billing/` | merged (move) |
| `p2/modul-billingu/02-…/07-glosariusz.md` | `final/glosariusz.md` | merged (fold) |

### docs/test-env/ (1 plik)

| Źródło | Cel | Status |
|---|---|---|
| `test-env/tpay-sandbox-runbook.md` | `final/troubleshooting/tpay-sandbox-runbook.md` | merged (move) |

### Poza zakresem (bez zmian)

| Ścieżka | Status |
|---|---|
| `docs/TestGEN/` (40 pl.) | KEEP — oryginalna specyfikacja produktu (punkt odniesienia) |
| `docs/sample-srs.md` | KEEP — przykład SRS bez referencji w kodzie |
| `backend/scripts/export_openapi.py` | KEEP — lokalne narzędzie dev; wskazuje historyczną ścieżkę, odświeżenie przy E8 (8-13) |

## 3. De-dualizacja (native-only)

Zgodnie z zasadą od konsolidacji E3: dokumentacja opisuje wyłącznie
deterministyczne silniki. Usunięte przy scalaniu:

- **Pliki**: E4 `08-dual-path.md` (59 linii), E5 `07-dual-path.md` (121 linii),
- **Wzmianki w treści** (17 plików E4/E5): sekcje „Tryby pracy"/„Model
  wykonawczy", `engine_mode` w przykładach JSON i tabelach modeli, wartości
  `llm`/`hybrid` w enumach `source`/`match_method`, wpisy confidence LLM,
  Q&A FAQ o trybach/timeoutach, wiersze tabel modułów
  (`dual_path_orchestrator`, `llm_*_analyzer`), gałęzie diagramów.
- Zachowany opis zachowań realnych: determinizm, offline, powtarzalność.

## 4. Naprawa referencji krzyżowych

- Linki relatywnie wewnątrz final/: `ai/` ↔ `adr/` ↔ `api/` (zmiana głębokości
  po rozbiórce na `ai-modules/`), przewodniki ↔ architektury modułów,
  FAQ → glosariusz wspólny.
- Odniesienia tekstowe (ścieżki w backtickach): E6/E7 → nowe lokalizacje
  billing/troubleshooting.
- Pliki poza `docs/`: `backend/app/main.py` (opis aplikacji — wcześniej
  wskazywał nieistniejącą ścieżkę sprzed konsolidacji 1.50),
  `backend/docs/README.md` (tabela przekierowań),
  `backend/tests/scenarios/README.md` (link do runbooka).

## 5. Kompletność (AC3)

Walidacja `scripts/validate_final_docs.py` (zielono = exit 0):

1. Każde źródło z inwentaryzacji ma wpis w mapie powyżej (125/125),
2. katalogi fazowe `docs/p1/`, `docs/p2/`, `docs/test-env/` nie istnieją
   (brak duplikacji),
3. wszystkie linki `.md` w `docs/final/` wskazują istniejące pliki,
4. `docs/final/` czysty native (wyjątek: niniejszy raport i inwentaryzacja —
   opisują co usunięto),
5. glosariusz ≥ 100 pozycji (138).

## 6. Kolejne kroki

- Story 9.2–9.12 wypełniają sekcje final/ (podręcznik, wdrożeniowa, admin,
  C4, moduły AI, troubleshooting, release notes).
- Dokumentacja Epic 8 (story 8-5/8-13) trafia bezpośrednio do
  `docs/final/architecture/api/` — katalogi fazowe nie wracają.
