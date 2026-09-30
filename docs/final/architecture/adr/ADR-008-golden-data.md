# ADR-008: Golden data do walidacji analiz

## Status

Accepted

## Kontekst

Wyniki analiz (klasyfikacja dokumentu, ekstrakcja wymagań, detekcja
niespójności, generowanie testów) mogą się zmieniać między uruchomieniami w
wyniku refaktoru — niekoniecznie celowo. Potrzebny jest mechanizm wykrywania
regresji: zamrożone, ręcznie przygotowane wyniki odniesienia, przeciw którym
wyjście bieżącego kodu jest porównywane.

## Decyzja

System **golden data** — zbiory dokumentów/kodu z ręcznie przygotowanym ground
truth. Wykonanie analizy porównuje rzeczywiste wyjście z zamrożonym, a testy
bramkowe (`test_doc_golden_metrics`, `docs_regression_checker.check_regression`)
failują pipeline przy regresji. Metryki baseline (accuracy, precision, recall)
utrzymywane per moduł z jawnymi progami.

Ground truth łączy zamrożone wyjście serwisów (liczności, teksty) z intencją
autorską (np. `has_intentional_discrepancies`). Zbiory:
`backend/tests/golden_data/` (moduł dokumentacji: `docs/`).

## Konsekwencje

**Pozytywne:**

- Wykrywanie subtelnych regresji zachowania analizy.
- Ślad audytu oczekiwanego zachowania; wsparcie testów regresyjnych.
- Ustalony baseline jakości dla ścieżki natywnej.

**Negatywne:**

- Zarządzanie cyklem życia danych odniesienia (regeneracja przy celowej zmianie).
- Dodatkowa pojemność dyskowa dla snapshotów.
- Wymaga dyscypliny: celowa zmiana zachowania = aktualizacja ground truth.

## Powiązane

- [ADR-006](./ADR-006-jinja2-template-engine.md) — golden data waliduje
  stabilność szablonów.
- [ai/benchmarks.md](../../ai-modules/analiza-kodu/benchmarks.md) — metryki baseline per moduł.
