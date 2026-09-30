# Parsowanie UML — pipeline natywny (Epic 3)

Od diagramu UML (PlantUML/XMI lub wizualnego SVG/PDF/raster) do ustrukturyzowanego
`ParsedUMLModel`, którym zasilane są rekonstrukcja przepływów (3.7), porównanie z
kodemu (3.4) i macierz śledzenia (3.15). Parsowanie oparte na regułach (gramatyka
PlantUML, XML `defusedxml`, OCR tekstu + geometria kształtów). Endpointy:
[uml_gui_examples.md](../../architecture/api/examples/uml_gui_examples.md); modele:
[uml-gui-data-models.md](./uml-gui-data-models.md).

## Etapy pipeline'u

```
Plik UML (upload)
  1. detect_format()   → UMLFormat (plantuml | xmi | svg | pdf | raster)
  2. detect_diagram_type() → DiagramType (sequence | use_case | class | activity | state_machine)
  3. parse()
       Tier 1 (plantuml/xmi)  → pełna ekstrakcja strukturalna (uczestnicy, elementy, relacje)
       Tier 2 (svg/pdf/raster) → analiza wizualna (OCR + kształty), source=ocr, confidence
  4. ParsedUMLModel → persystencja JSONB → downstream (3.7 cross-diagram, 3.4 compare-code, 3.15)
```

Każdy model utrwalany w `parsed_uml_models` (JSONB); `source` (`parser`|`ocr`) i
`confidence` sygnalizują wierność ekstrakcji.

## Formaty (macierz: format × typ diagramu)

| Format | Typ diagramu | Status |
|---|---|---|
| **PlantUML** (`@startuml`) | wszystkie 5 | **pełne** — strukturalna ekstrakcja (Tier 1) |
| **XMI** (UML 2.x, OMG/Eclipse) | wszystkie 5 | **częściowe/pełne** — klasy pełne, pozostałe częściowe (zależność od wersji/narzędzia) |
| **SVG** | wszystkie 5 | **OCR** — `defusedxml` wektor, najwyższa wierność Tier 2, bez deps binarnych |
| **PDF** | wszystkie 5 | **OCR** — PyMuPDF + OCR; graceful degrade bez deps |
| **PNG/JPEG** (raster) | wszystkie 5 | **OCR** — cv2 + Tesseract/EasyOCR; graceful degrade bez deps |

> Tier 2 (SVG/PDF/raster, Story 3.1b + domknięcie 3-1b): analiza opiera się na
> OCR tekstu i wnioskowaniu kształtów (prostokąt→klasa, owal→use case,
> romb→decyzja, strzałka→relacja). Wynik oznaczony `source: ocr` z `confidence`.
> Akceptację rozszerzeń definiuje `UML_ALLOWED_EXTENSIONS` (`upload_service.py`).

## Wykrywanie formatu i typu

- **Format** (`detect_format`/`detect_format_from_content`, `uml/upload_service.py`):
  rozszerzenie (`.puml`/`.xmi`/`.svg`/`.pdf`/`.png`) → magic bytes (`%PDF`, `\x89PNG`,
  `<svg`, `@startuml`, `<?xml`/`<xmi`) → heurystyka (`<` → XMI, inaczej PlantUML).
- **Typ** (`detect_diagram_type`): PlantUML — markery strukturalne + słowa kluczowe
  (`class`/`interface`/`enum`, `start`/`stop`/`if`, `[*]`/`state`); XMI — nazwy
  elementów regex; wizualne — skład kształtów (`classify_visual_diagram_type`,
  `uml/visual/shapes.py`).

## Adapter visual→structural (domknięcie 3-1b)

Kluczowa decyzja: parser wizualny (`build_visual_model`, `uml/visual/shapes.py`)
emituje **zarówno** pola wizualne (`element_type`, `bbox`), **jak i strukturalne**
— tak, żeby downstream pisany pod schema strukturalne widział elementy z OCR:

- klasy (rect+CLASS) → `element_kind` (`class`/`interface`/`enum`) + stabilne `id` (`v{idx}`)
- węzły activity → `node_type` (`start`/`stop`/`action`/`decision`)
- węzły state → `is_initial`/`is_final`
- relacje → rozwiązywane `source_id`/`target_id` (obok name-based `source`/`target`)

Bez tego cross-diagram (3.7) i compare-code (3.4) po cichu dostawały puste wyniki.
Heurystyka start/stop z topologii DAG + etykiet (OCR nie widzi wypełnionego kółka).
Patrz [ADR-011](../../architecture/adr/ADR-011-uml-visual-tier2.md).

## compare-code (3.4 + domknięcie 3-1b)

`POST /projects/{id}/uml/{diagram_id}/compare-code` porównuje klasy z diagramu z
kodemu projektu (`logic_structures`, Epic 1). Dyskryminacja `interface`/`enum` po
`element_kind`. `ClassMatch.attribute_match_pct`/`method_match_pct: float | None`:
przy zerowej liczbie成员 ekstrahowanych z diagramu ( inherentne dla OCR) comparator
zwraca `null`, a nie vacuous `100%` — uczciwe sygnalizowanie niepełnej ekstrakcji.

## Ograniczenia (udokumentowane, szczere)

- **OCR nie ekstrahuje成员 klasy** (atrybuty/metody) — inherentne; compare-code
  raportuje `*_match_pct = null`.
- **Dyskryminacja interface/enum z OCR niewyprowadzalna** — wszystkie klasy z OCR
  to `element_kind="class"` (brak markera wizualnego).
- **`classify_visual_diagram_type` nigdy nie zwraca `state_machine`** (diamond →
  activity×3 > state×1) — wizualne diagramy stanów bywają misklasyfikowane jako
  activity; golden dataset odzwierciedla empirycznie detekowany typ.
- XMI: zależność od wersji (2.1/2.5) i narzędzia; bezpieczny XML (`defusedxml`).

## Moduł → serwis → story

| Komponent | Serwis | Story |
|---|---|---|
| upload + detect | `UMLUploadService` | 3.1 |
| parser sekwencji/use-case/klas/aktywności/stanów | `uml/parsers/*` | 3.2–3.6 |
| parser wizualny (Tier 2) | `uml/visual/*` (`build_visual_model`) | 3.1b, 3-1b |
| cross-diagram → flows | `CrossDiagramAnalyzer` | 3.7 |
| compare-code | `class_code_comparator` | 3.4, 3-1b |

## Powiązane

- [gui-analysis.md](./gui-analysis.md) — osobny pipeline screenshotów GUI.
- [test-generation-uml-gui.md](./test-generation-uml-gui.md) — flows → Gherkin → kod.
- [ADR-011](../../architecture/adr/ADR-011-uml-visual-tier2.md), [ADR-008](../../architecture/adr/ADR-008-golden-data.md).
