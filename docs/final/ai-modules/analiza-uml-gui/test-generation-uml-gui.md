# Generowanie testów z UML/GUI — pipeline natywny (Epic 3)

Od zrekonstruowanych przepływów użytkownika (`UserFlow`) do scenariuszy BDD
(`GherkinFeature`) i kodu testowego (`TestCode`: Cypress / SikuliX). Mapowanie
oparte na regułach + szablonach Jinja2. Endpointy:
[uml_gui_examples.md](../../architecture/api/examples/uml_gui_examples.md); modele:
[uml-gui-data-models.md](./uml-gui-data-models.md).

## Etapy pipeline'u

```
ParsedUMLModel / GUIScreenshot
  1. Rekonstrukcja user flows (cross-diagram 3.7 / sekwencja ekranów 3.9)
       → UserFlow → FlowStep (z metadanymi relacji/decyzji)
  2. Mapowanie flows → Gherkin (3.11)
       include → Background | extend → Scenario Outline+Examples | decyzje → Scenarios
       → GherkinFeature (status: generated → validated → approved)
  3. Codegen (3.12 Cypress / 3.13 SikuliX) z zatwierdzonych feature'ów
       → TestCode (Cypress: DOM; SikuliX: image-based + realne PNG)
```

## Rekonstrukcja przepływów (3.7 / 3.9)

- **Cross-diagram (3.7, `CrossDiagramAnalyzer`)** — łączy diagramy UML jednego
  projektu: participant→klasa, klasa→state machine, rekonstrukcja activity/state.
  Po domknięciu 3-1b czyta również elementy z OCR (`element_kind`/`node_type`).
- **GUI (3.9, `gui/flow_service.py`)** — sekwencja screenshotów → przepływ przez
  komponenty; `meta` niesie `action_type`/`confidence` (include/extend/decyzje N/A).

`FlowStep` niesie akcję, aktora, cel, oczekiwany rezultat, źródło (`source_diagram_id`/
`source_screenshot_id`) oraz **`metadata`** (JSONB, domknięcie 3-11).

## Mapowanie Gherkin (3.11, `gherkin_mapper.py`) — domknięcie 3-11

`FlowStep.metadata` przenosi semantykę relacji UML, którą mapper tłumaczy realnie
(nie heurystyką):

| `metadata.relation_type` | Wynik w `.feature` |
|---|---|
| `include` | sekcja `Background` z relacji include (nie wspólny prefiks Given) |
| `extend` + `parameters` | `Scenario Outline` + `Examples` (auto-detekcja) |
| — (z `branch_label`) | rozgałęzienia decyzyjne → osobne `Scenario` (grupowanie po etykiecie) |

Szablon `gherkin_feature.jinja2` + `validate_gherkin` wspierają Background/Outline/Examples.
Wsteczna zgodność: flows bez `metadata` (legacy) → identycznie jak dotychczas
(`flow_to_scenario` + heuristic background). Dodatkowo `_reconstruct_use_case`
(use-case produkuje flow — wcześniej nie produkował wcale).

## Codegen (3.12 / 3.13)

Z `GherkinFeature` o `status=approved` generowany jest `TestCode`:

- **Cypress (3.12)** — DOM-based (selektory); generyczna ścieżka `generate_code_for_test_cases(framework="cypress")`.
- **SikuliX (3.13)** — image-based; dedykowany `sikulix_pipeline.generate_sikulix_code`
  wycina realne PNG ze screenshotów (domknięcie 3-13, zob. [gui-analysis.md](./gui-analysis.md)).

`TestCode.framework` = `cypress` | `sikulix`; `pattern_images` (JSONB) tylko dla SikuliX.

## Moduł → serwis → story

| Komponent | Serwis | Story |
|---|---|---|
| rekonstrukcja flows (UML) | `CrossDiagramAnalyzer` | 3.7 |
| rekonstrukcja flows (GUI) | `gui/flow_service.py` | 3.9 |
| Gherkin mapper | `gherkin_mapper.py` | 3.11, 3-11 |
| codegen Cypress | `test_generation/*` (Jinja2) | 3.12 |
| codegen SikuliX + PNG | `sikulix_pipeline.py`, `pattern_cropper.py` | 3.13, 3-13 |

## Powiązane

- [uml-parsing.md](./uml-parsing.md), [gui-analysis.md](./gui-analysis.md) — źródła flows.
- [traceability-uml-gui.md](./traceability-uml-gui.md) — macierz źródło→test→kod.
- [ADR-006](../../architecture/adr/ADR-006-jinja2-template-engine.md), [ADR-012](../../architecture/adr/ADR-012-sikulix-image-based.md).
