# Architektura modułu luk funkcjonalnych — przegląd

> Moduł luk funkcjonalnych TestGEN (Epic 5).
> Wersja odpowiada implementacji w `backend/app/services/gap_analysis/`.

## 1. Cel modułu

Moduł luk funkcjonalnych porównuje wymagania z dokumentacji (SRS, SDD, user
stories) z faktycznie zaimplementowanym kodem i produkuje ustrukturyzowaną listę
luk wraz z oceną zgodności (compliance) oraz rekomendacjami naprawczymi.

Główne funkcje (FR38–FR42):

- **FR38** — Dopasowanie wymagań do bytów kodu (fuzzy + semantic matching)
- **FR39** — Klasyfikacja luk w 4 kategoriach: `missing`, `different`, `extra`, `inconsistent`
- **FR40** — Compliance scoring na poziomie projektu / modułu / funkcji
- **FR41** — Detekcja błędów kodu (syntax, logic, semantic, conformance)
- **FR42** — Rekomendacje + skeleton code generator + integracja z trackerami

## 2. Diagram pipeline'u

```
                ┌────────────────────────────────────────┐
                │  Wejście                                │
                │  • AnalysisResult(module="requirements")│
                │  • AnalysisResult(module="logic_structures")│
                └──────────────────┬─────────────────────┘
                                   ▼
                       ┌────────────────────────┐
                       │  ComparatorService      │
                       │  (Levenshtein + JW +    │
                       │   TF-IDF cosine)        │
                       └───────────┬─────────────┘
                                   ▼
                       ┌────────────────────────┐
                       │  GapClassifier          │
                       │  (4 typy + severity +   │
                       │   context excerpts)     │
                       └───────────┬─────────────┘
                                   ▼
                ┌──────────────────────────────────────────┐
                │  Persystencja: gap_findings (RLS)         │
                └──────────────────┬───────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
  ┌──────────────┐        ┌────────────────┐        ┌────────────────┐
  │ComplianceEng │        │RecommendationEng│        │ SkeletonGen    │
  │ (project /   │        │ (templates +   │        │ (Jinja2 per    │
  │  module /    │        │  priority +    │        │  język +       │
  │  function)   │        │  confidence)   │        │  tree-sitter)  │
  └──────┬───────┘        └────────┬───────┘        └────────┬───────┘
         │                         │                         │
         ▼                         ▼                         ▼
  ┌──────────────┐        ┌────────────────┐        ┌────────────────┐
  │ComplianceSnap│        │IntegrationsSync│        │ Code preview   │
  │ (trend + diff│        │ (Jira / ADO)   │        │ (modal UI)     │
  │  v1 vs v2)   │        └────────────────┘        └────────────────┘
  └──────────────┘
```

## 3. Moduły i ich odpowiedzialności

| Moduł | Plik | Rola |
|---|---|---|
| Comparator | `comparator.py` | Fuzzy matching wymagań z bytami kodu (3 algorytmy) |
| Classifier | `classifier.py` | Klasyfikacja w 4 typy luk + przypisanie severity |
| Classification rules | `classification_rules.py` | Thresholds, exclude patterns, severity map |
| Compliance engine | `compliance_engine.py` | Scoring 0–100 per projekt/moduł/funkcja |
| Error detectors | `error_detectors/` | Syntax / logic / semantic / conformance |
| Recommendation engine | `recommendation_engine.py` | Rekomendacje na podstawie reguł i szablonów |
| Skeleton generator | `skeleton_generator.py` | Jinja2 + tree-sitter (Python/TS/Java/C#) |
| Comparison engine | `comparison_engine.py` | Diff snapshotów v1↔v2 + trend |
| Integrations | `integrations/jira_service.py`, `integrations/azure_devops_service.py` | Sync do trackerów |

## 4. Tryb pracy

Analiza działa na deterministycznych algorytmach (Levenshtein, Jaro-Winkler,
TF-IDF cosine): offline, bez zależności od usług zewnętrznych, z gwarancją
powtarzalności wyników — te same dane wejściowe dają ten sam wynik.

## 5. Model danych

Wszystkie znaleziska są persystowane w dedykowanej tabeli `gap_findings` (wzorzec
Epic 4) z RLS per-tenant. Pozwala na niezależne filtrowanie, paginację i zapytania
cross-analysis, których nie obsługuje JSONB w `AnalysisResult.result_data`.

Powiązane tabele:

- `gap_findings` — znaleziska luk (4 typy + source + match_score)
- `code_errors` — błędy kodu (4 kategorie)
- `recommendations` — rekomendacje naprawcze z confidence i priority
- `compliance_snapshots` — punkt w czasie dla porównań wersji
- `integration_configs` + `integration_sync_logs` — konfiguracja i logi sync do trackerów

Szczegóły: [09 — Modele danych](09-modele-danych.md).

## 6. Przepustowość i ograniczenia

- Comparator: O(R×E) par dopasowania (R = wymagania, E = byty kodu). Dla typowych
  projektów (dziesiątki do niskich setek wymagań) < 1 s.
- Skeleton generator: tree-sitter waliduje składnię; 1 plik na finding type=missing.

## 7. Powiązane dokumenty

- [02 — Comparator](02-comparator.md)
- [03 — Klasyfikator luk](03-klasyfikator-luk.md)
- [04 — Compliance engine](04-compliance-engine.md)
- [05 — Recommendation engine](05-recommendation-engine.md)
- [06 — Skeleton generator](06-skeleton-generator.md)
- [08 — Integracje](08-integracje.md)
- [09 — Modele danych](09-modele-danych.md)
