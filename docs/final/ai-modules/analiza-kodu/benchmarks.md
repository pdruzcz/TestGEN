# Benchmarki i golden data (P1)

Zamrożone metryki baseline dla ścieżki natywnej, walidowane zestawami golden
data ([ADR-008](../../architecture/adr/ADR-008-golden-data.md)). Służą detekcji regresji:
zmiana kodu psująca metrykę failuje pipeline.

## Koncepcja

Golden data to dokumenty/kod z **ręcznie przygotowanym ground truth**, przeciw
któremu testy regresyjne porównują bieżące wyjście serwisów. Ground truth łączy
zamrożone wyjście (liczności, teksty) z intencją autorską (np.
`has_intentional_discrepancies`).

## Moduł dokumentacji (Epic 2)

Zbiór: 10 polskojęzycznych dokumentów (PDF=4, DOCX=3, MD=2, HTML=1; 5 spójnych /
5 z celowymi niespójnościami). Pełny opis i instrukcja regeneracji:
[`backend/tests/golden_data/docs/README.md`](../../../../backend/tests/golden_data/docs/README.md).

### Próbki (10)

| # | Kategoria | Format | Nazwa | Celowe niespójności |
|---|-----------|--------|-------|---------------------|
| 1 | srs | pdf  | srs_system_logowania        | nie |
| 2 | srs | docx | srs_platnosci               | TAK |
| 3 | srs | md   | srs_raporty                 | nie |
| 4 | brd | pdf  | brd_system_logowania        | TAK |
| 5 | brd | docx | brd_platnosci               | TAK |
| 6 | frd | pdf  | frd_modul_uzytkownikow      | TAK |
| 7 | frd | html | frd_profil_uzytkownika      | nie |
| 8 | manual | docx | podrecznik_administratora | nie |
| 9 | manual | md   | podrecznik_operatora      | TAK |
| 10 | instruction | pdf | instrukcja_instalacji | nie |

### Metryki baseline

| Moduł | Metryka | Próg | Opis |
|-------|---------|------|------|
| Klasyfikacja | accuracy | 0.90 | % poprawnie sklasyfikowanych typów |
| Ekstrakcja wymagań | recall | 0.80 | % ground-truth wymagań znalezionych |
| Ekstrakcja wymagań | precision | 0.80 | % znalezionych w ground truth |
| Detekcja niespójności | recall | 0.80 | % celowych niespójności wykrytych |
| Glosariusz | recall | 0.80 | % ground-truth terminów znalezionych |

Progi: [`backend/tests/golden_data/docs_thresholds.json`](../../../../backend/tests/golden_data/docs_thresholds.json).
Test bramkowy `test_doc_golden_metrics` agreguje metryki i failuje pipeline
przy regresji (`docs_regression_checker.check_regression`).

### Wykrywalne typy niespójności

W golden data istotne są `duplicate` i `missing_reference` — występują
wyłącznie w próbkach z celowymi niespójnościami. Typ `terminology` traktowany
jako szum detektora („System"/„Użytkownik" w 3+ wymaganiach) i celowo pomijany
w asercjach.

## Moduł kodu (Epic 1)

Analiza AST i generowanie przypadków testowych są deterministyczne
([ast-analysis.md](./ast-analysis.md)), stąd baseline jakości opiera się na
stabilności wyjścia między uruchomieniami i pokryciu struktur kodu przypadkami
testowymi. Regresje wykrywane przez porównanie z zamrożonym wyjściem analizy.

## Uruchamianie

```bash
cd backend
pytest tests/golden_data/ -m golden -v                              # cały zbiór golden
pytest tests/golden_data/test_document_classification_golden.py -v  # tylko dokumenty
```

## Aktualizacja

Metryki aktualizować po każdym release. Celowa zmiana zachowania analizy =
regeneracja ground truth (generatory `_generate_samples.py`,
`_generate_ground_truth.py`), nie obniżenie progu.
