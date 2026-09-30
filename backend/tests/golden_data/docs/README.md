# Golden data — moduł dokumentacji (Epic 2, Story 2.11)

Zbiór 10 polskojęzycznych dokumentów referencyjnych z zamrożonym *ground truth*,
walidujących **natywną** ścieżkę analizy dokumentacji: parsowanie →
preprocessing → klasyfikacja → ekstrakcja wymagań → detekcja niespójności →
glosariusz. Każda próbka przechodzi pełny pipeline; testy regresyjne weryfikują
stabilność i jakość wyjścia względem progów w `docs_thresholds.json`.

> Zgodnie z decyzją architektoniczną zbiór modeluje **wyłącznie tryb native**
> aplikacji. Tryby LLM/hybdrydowe nie występują w dokumentacji ani w założeniach
> tego zbioru.

## Układ katalogów

```
tests/golden_data/docs/
├── _generate_samples.py          # generator binariów (PDF/DOCX) + MD/HTML
├── _generate_ground_truth.py     # konsolidator *_ground_truth.json (z probe)
├── srs/    <name>.<ext> + <name>_ground_truth.json
├── brd/    …
├── frd/    …
├── manual/ …
└── instruction/ …
```

## Próbki (10)

| # | Kategoria | Format | Nazwa | Niespójności | Klasyfikacja |
|---|-----------|--------|-------|--------------|--------------|
| 1 | srs | pdf  | srs_system_logowania        | nie  | specyfikacja_wymagań |
| 2 | srs | docx | srs_platnosci               | **TAK** (dup + missing-ref) | specyfikacja_wymagań |
| 3 | srs | md   | srs_raporty                 | nie  | specyfikacja_wymagań |
| 4 | brd | pdf  | brd_system_logowania        | **TAK** (dup + missing-ref) | specyfikacja_wymagań |
| 5 | brd | docx | brd_platnosci               | **TAK** (dup + missing-ref) | specyfikacja_wymagań |
| 6 | frd | pdf  | frd_modul_uzytkownikow      | **TAK** (dup + missing-ref) | specyfikacja_wymagań |
| 7 | frd | html | frd_profil_uzytkownika      | nie  | specyfikacja_wymagań |
| 8 | manual | docx | podrecznik_administratora | nie  | podręcznik_użytkownika |
| 9 | manual | md   | podrecznik_operatora      | **TAK** (dup) | podręcznik_użytkownika |
| 10 | instruction | pdf | instrukcja_instalacji | nie  | instrukcja_techniczna |

Pokrycie: PDF=4, DOCX=3, MD=2, HTML=1. Rozkład: 5 spójnych / 5 z celowymi
niespójnościami (AC2).

## Konwencje

- **Nazewnictwo**: `<name>.<ext>` + `<name>_ground_truth.json` (auto-discovery
  przez `rglob`, spójne z golden data UML/GUI).
- **Ground truth** = zamrożone wyjście serwisów + intencja autorska (typ
  dokumentu, `has_intentional_discrepancies`). Liczności są deterministyczne
  (regex/słowniki, bez losowości w tekście — ID wymagań używają `hash()`, ale
  testy dopasowują **tekst**, nie ID).
- **Wykrywalne typy niespójności** (`duplicate`, `missing_reference`) występują
  WYŁĄCZNIE w próbkach rozbieżnych. Typ `terminology` jest traktowany jako **szum
  detektora** (kapitalizowane „System"/„Użytkownik" powtarzające się w 3+
  wymaganiach) i celowo pomijany w asercjach.

## Regeneracja

Po zmianie treści próbek lub serwisów:

```bash
cd backend
python -m tests.golden_data.docs._generate_samples       # binaria + MD/HTML
python -c "import tests.golden_data.docs._generate_ground_truth as g"  # wymaga _probe_out.json
```

Pełny cykl konsolidacji (probe → ground truth):

```bash
# 1. dump wyjścia serwisów do _probe_out.json (skrypt probe, patrz historia Story 2.11)
# 2. python -m tests.golden_data.docs._generate_ground_truth
```

> Generator PDF wymaga fontu TTF z obsługą Latin-Extended (Arial na Windows,
> DejaVuSans na Linux/macOS). Domyślne fonty reportlab (Helvetica) psują polskie
> znaki w warstwie tekstowej. Binaria regeneruje się na maszynie deweloperskiej;
> CI jedynie parsuje commitowane pliki.

## Uruchamianie

```bash
cd backend
pytest tests/golden_data/ -m golden -v          # cały zbiór golden
pytest tests/golden_data/test_document_classification_golden.py -v   # tylko dokumenty
```

## Metryki i regresja (AC3)

`test_doc_golden_metrics.py` agreguje per-moduł: klasyfikacja accuracy,
ekstrakcja wymagań recall/precision, detekcja niespójności recall, glosariusz
recall. `docs_regression_checker.check_regression` porównuje z progami w
`docs_thresholds.json` — pipeline CI fails przy spadku poniżej progu. Progi
(acc 0.90, pozostałe 0.80) dają margines poniżej zamrożonego baseline'u (=1.0).

## Znane odchylenia od literału story

- `brd_platnosci.docx` zostało przekształcone z „spójnego" na dokument z celowymi
  niespójnościami, aby spełnić AC2 (5/5); pozostałe 5 dokumentów jest spójnych.
- `frd_modul_uzytkownikow.html` nosi nazwę `frd_profil_uzytkownika.html`
  (uniknięcie kolizji nazw ground-truth z odpowiednikiem PDF — story używało
  sufiksu `_v2`).
- Brak `jsonschema` — walidacja ground truth jest lekka (liczności + dopasowanie
  tekstu), spójna z konwencją golden data Epic 3/4.
