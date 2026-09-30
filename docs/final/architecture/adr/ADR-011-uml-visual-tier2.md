# ADR-011: UML wizualne Tier 2 (SVG/PDF/raster) + adapter visual→structural

## Status

Accepted

## Kontekst

Pierwotnie parser UML przyjmował wyłącznie formaty semantyczne (Tier 1: PlantUML,
XMI) — `UMLFormat = {xmi, plantuml}`. Story 3.1b rozszerzyła listę o formaty
wizualne: **SVG, PDF, PNG/JPEG** (`{xmi, plantuml, svg, pdf, raster}`), parsowane
przez OCR tekstu i wnioskowanie kształtów (`uml/visual/`).

Pojawił się szew między parserem wizualnym a downstream: `build_visual_model`
emitował elementy z polami wizualnymi (`element_type`, `bbox`, name-based
`source`/`target`), podczas gdy cross-diagram (3.7) i compare-code (3.4) czytały
**strukturalne** schema (`element_kind`, `id`, `node_type`, `is_initial`/`is_final`,
`source_id`/`target_id`). W efekcie diagramy z OCR po cichu produkowały puste
mapowania i puste user flows z `status=COMPLETED` — pipeline raportował sukces,
a realnie downstream był pusty (groźniejsze niż jawny stub).

## Decyzja

**Root-fix w producerze** (`build_visual_model`, `uml/visual/shapes.py`, domknięcie
3-1b): parser wizualny emituje **zarówno** pola wizualne, **jak i strukturalne** —
klasy → `element_kind` (`class`/`interface`/`enum`) + stabilne `id` (`v{idx}`);
węzły activity → `node_type` (`start`/`stop`/`action`/`decision`); węzły state →
`is_initial`/`is_final`; relacje → `source_id`/`target_id`. Każdy model Tier 2
oznaczony `source: ocr` + `confidence` (0.0–1.0).

Wybrano root-fix w producerze zamiast izolowanego adaptera w konsumerze, bo
compare-code (3.4) i traceability (3.15) czytają elementy **wprost z persystowanego
JSONB** — adapter w cross-diagram naprawiłby tylko 3.7. Heurystyka start/stop z
topologii DAG + etykiet (OCR nie widzi wypełnionego kółka).

## Konsekwencje

**Pozytywne:**

- Diagramy z OCR realnie zasilać cross-diagram (3.7), compare-code (3.4),
  traceability (3.15) — spójne schema niezależnie od źródła.
- `ClassMatch.*_match_pct: float | None` — koniec vacuous `100%` przy braku成员;
  uczciwe `null` sygnalizuje niepełną ekstrakcję.

**Negatywne:**

- OCR inherentnie nie ekstrahuje成员 klasy (atrybuty/metody) ani nie dyskryminuje
  interface/enum (brak markera wizualnego) — udokumentowane ograniczenie.
- `classify_visual_diagram_type` nigdy nie zwraca `state_machine` (kandydat na
  osobne domknięcie classifiera).

## Powiązane

- [ai/uml-parsing.md](../../ai-modules/analiza-uml-gui/uml-parsing.md) — adapter + compare-code.
- [ADR-008](./ADR-008-golden-data.md) — golden SVG weryfikuje ścieżkę wizualną.
- Domknięcie `3-1b` (`_bmad-output/implementation-artifacts/E3/3-1b-domkniecie.md`).
