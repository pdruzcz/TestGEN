# Golden test data — UML i GUI (Epic 3, Story 3.14)

Wyselekcjonowany zbiór danych referencyjnych ("golden data") dla parserów UML,
analizy GUI i silnika regresji wizualnej. Każdy artefakt ma zamrożony *ground
truth*, względem którego testy regresyjne weryfikują, że zmiany w kodzie nie
psują dotychczasowych wyników.

## Układ katalogów

```
tests/golden_data/
├── uml/<typ>/<nazwa>.puml|.xmi                 # diagram PlantUML lub XMI (25 + 5)
│   └── <nazwa>_ground_truth.json              # oczekiwane liczności elementów
├── uml/visual/<nazwa>.svg                      # diagram UML SVG (Tier 2, 5 typów)
│   └── <nazwa>_ground_truth.json              # source=ocr + liczniki + accuracy
├── gui/<kategoria>/<nazwa>.png                 # syntetyczny zrzut GUI (image-gated)
│   └── <nazwa>_ground_truth.json              # inwentarz komponentów
├── visual_regression/<nazwa>_{baseline,comparison}.png  # para obrazów (image-gated)
│   └── <nazwa>_ground_truth.json              # para baseline/comparison + werdykt
├── code_samples/                              # (istniejące) próbki kodu Py/Java/C#
├── conftest.py                                # loadery + fixture'y auto-discovery
├── test_uml_parsers_golden.py                 # @pytest.mark.golden (text + visual SVG)
├── test_gui_analysis_golden.py                # @pytest.mark.golden (schema inwentarza)
├── test_gui_png_golden.py                     # @pytest.mark.golden (PNG image-gated)
└── test_visual_regression_golden.py           # @pytest.mark.golden (semantic-diff)
```

## UML (30 próbek: 25 PlantUML + 5 XMI)

PlantUML + XMI, po 6 na typ diagramu (5 puml + 1 xmi): `sequence`, `use_case`,
`class`, `activity`, `state_machine`. Każdy plik `*_ground_truth.json` zawiera
`diagram_type` oraz oczekiwane liczności: `expected_participants_count`,
`expected_elements_count`, `expected_relationships_count`,
`expected_fragments_count`, `expected_flows_count`.

Liczności zostały **zamrożone z faktycznego wyjścia** `UMLParserOrchestrator`
(weryfikacja jednorazowa), a porównanie używa tolerancji: brakujące elementy
mogą stanowić < 10 % oczekiwanej liczby (AC-2). Detekcja typu diagramu jest
sprawdzana dokładnie.

## Visual SVG (5 diagramów, Tier 2)

Diagramy UML w formacie SVG (`class`, `use_case`, `activity`, `sequence` oraz
reprezentacja `state_machine`) parsowane ścieżką wizualną `VisualUMLParser.parse_svg`
(`source = ocr`, `defusedxml`, bez binariów CV/OCR). Każdy GT zawiera liczniki,
`expected_source: ocr` i `expected_element_names` dla bramki accuracy ≥ 70 %.

> **Nota — `state_machine`.** Klasyfikator wizualny (`classify_visual_diagram_type`)
> nie osiąga `STATE_MACHINE` (diamonds→ACTIVITY×3 > STATE×1); semantyczny diagram
> stanu jest w zbiorze, ale GT `diagram_type` odzwierciedla empirycznie detekowany
> typ (`class`). Kandydat na osobne domknięcie classifiera.

## GUI (81 próbek: 18 syntetycznych + 63 realne) + PNG — macierz pokrycia 11 typów

Zbiór NFR-ACC-001 (Story 3-14c): **≥ 80 PNG z GT, realne ≥ 60** (63), syntetyk
**≤ 20** (18), a każdy z **11 typów** `GUIComponentType` ma **≥ 10 wystąpień GT**
w całym zbiorze (licznik wystąpień w `expected_components`, nie screenshotów):

| typ | button | input | dropdown | checkbox | radio | menu | link | table | form | modal | tab |
|---|---|---|---|---|---|---|---|---|---|---|---|
| wystąpienia GT | 135 | 102 | 82 | 30 | 13 | 89 | 49 | 23 | 18 | 10 | 26 |

`unknown` celowo poza metryką. Bramki always-on w `test_gui_png_golden.py`:
`test_gui_pngs_are_rendered` (podłoga 80), `test_gui_real_ui_share` (real ≥ 60,
syntetyk ≤ 20), `test_gui_type_coverage` (≥ 10/typ + stany interakcji — patrz
`gui/real/README.md`). Raport per-typ (GT vs detekcja vs ratio) trafia do
`golden-accuracy.json` (`scripts/golden_accuracy.py`, AC4) — parser testowany
jednostkowo (`tests/unit/services/analysis/test_golden_accuracy_gui_types.py`).

Kategorie syntetyczne: `forms`, `dashboards`, `tables`, `navigation`, `modals`
(po 3, modals 6 — dorynkowanie typu modal 3-14c). Kategorie realne: `real`
(43) i `real_dense` (20 — gęste layouty docs z własnym sufitem widełek ratio;
uzasadnienie w `test_gui_png_golden.py` i `gui/real/README.md`).

Każdy plik opisuje oczekiwany inwentarz komponentów (`component_type`, `label`,
`bbox`, `confidence`) dla reprezentatywnego ekranu.

`scripts/generate_gui_png.py` renderuje syntetyczny zrzut PNG dla każdej próbki
syntetycznej (prostokąty komponentów wg zamrożonego *bbox* + etykiety); realne
PNG są przechwytywane Playwright (`backend/scripts/capture_real_ui.js`) i
commitowane. Te same obiekty `GoldenGUISample` (pole `png_path`) można podać
wprost do `GUIAnalyzerOrchestrator`. Testy PNG są **image-gated**: always-on
walidują obecność i pokrycie bbox (Pillow); detekcja komponentów
(`cv2`/`numpy`) uruchamia się tylko gdy imaging zainstalowany
(`pip install -e ".[imaging]"`), inaczej skip z adnotacją.

## Regresja wizualna (5 par)

Pary `baseline`/`comparison` jako listy komponentów + oczekiwany
`ComparisonStatus` i typy zmian. Pokrywają: brak zmian (MATCH), przesunięcie
elementu, usunięcie kontenera (breaking → MAJOR_DIFF), zmianę tekstu i dodanie
elementu. Wykorzystują czysto-pythonową ścieżkę `compute_component_delta` +
`classify_status` (bez zależności obrazowych), więc działają w każdym środowisku.

## Uruchamianie

```bash
pytest -m golden                       # cały zbiór golden
pytest tests/golden_data -q            # to samo, po ścieżce
```

Marker `golden` jest zarejestrowany w `pyproject.toml`. Testy automatycznie
wykrywają próbki (`rglob`), więc **dodanie nowego pliku** z `_ground_truth.json`
rozszerza pokrycie bez modyfikacji kodu testów.

## CI/CD

Sugerowany krok w pipeline (po unit testach, przed integracyjnymi):

```yaml
- name: Golden regression (UML/GUI)
  run: pytest -m golden --maxfail=1
```

Szybkie (~0.1 s), bez zależności sieciowych i obrazowych — nadają się jako
bramka regresyjna przy każdej zmianie parserów UML/GUI.

## Realizacja domknięcia 3-14 (2026-07-13)

Poprzednie odroczenia zamknięte w `3-14-domknięcie`:

- **PNG GUI fixtures** — ZREALIZOWANE: `scripts/generate_gui_png.py` renderuje
  15 zrzutów GUI + 10 PNG par visual_regression (baseline/comparison); testy
  image-gated (`test_gui_png_golden.py`).
- **XMI** — ZREALIZOWANE: 5 próbek XMI (po 1/typ), routing przez `detect_format`
  → `_parse_content`, `discover_uml_samples` rozpoznaje `*.xmi`.
- **Gęstość zbioru** — ZREALIZOWANE: 6 próbek/typ UML (5 puml + 1 xmi), 25 puml
  łącznie (vs. pierwotne 10).
- **Visual SVG** — DODANE: 5 diagramów SVG, harness `_parse_visual` (source=ocr,
  accuracy ≥ 70 %) — jedno źródło prawdy (wchłonęło `test_visual_golden.py`).
- **CI** — DODANY: stage `golden-regression` w `bitbucket-pipelines.yml` +
  artefakt `golden-accuracy.json` + threshold-gate (`scripts/golden_accuracy.py`).

Pozostały kandydat na osobne domknięcie: klasyfikator wizualny nie osiąga
`STATE_MACHINE` (patrz nota wyżej) — poza zakresem tego zbioru danych.
