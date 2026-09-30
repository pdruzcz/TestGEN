# Macierz śledzenia UML/GUI — pipeline natywny (Epic 3)

Od elementów źródłowych (UML/GUI) do macierzy łączącej je z przepływami, scenariuszami
Gherkin i pokryciem. Budowa regułowa; eksport CSV/XLSX/PDF. Endpointy:
[uml_gui_examples.md](../../architecture/api/examples/uml_gui_examples.md); modele:
[uml-gui-data-models.md](./uml-gui-data-models.md).

> Uwaga: `/projects/{id}/traceability` (Epic 3) to macierz **źródeł UML/GUI** — odrębna
> od traceability dokumentu (Epic 2, zob. [document-analysis.md](../analiza-dokumentacji/document-analysis.md)).

## Etapy pipeline'u

```
Elementy źródłowe (UML parsed / GUI components) + UserFlow + GherkinFeature
  1. _collect_uml_elements / GUI components  → pozycje macierzy
  2. _element_type (czyta element_kind)       → kanoniczny typ (spójny OCR vs parser)
  3. linkage: element → flow → gherkin       → coverage_status
  4. persystencja: TraceabilityMatrix (source/confidence) + summary
  → GET /traceability (matrix + summary) | /traceability/export (csv|xlsx|pdf|json)
```

## Spójność typów post-3-1b (domknięcie 3-15)

`_element_type` (`traceability_service.py`) czyta `element_kind` **pierwsze**
(kanoniczny dyskryminator strukturalny), potem `element_type`, potem `type`. Dzięki
temu klasa z OCR (`element_type="class"`) i z XMI (`element_kind="class"`) → obie
`"class"` (koniec asymetrii „class vs element"). Mapa `_UML_TYPE_MAP` uzupełniona o
tokeny wizualne: `decision`→activity, `enum`→class; `node` dwuznaczny → rozwiązywany
parametrem `category` (`activity`/`state_machine`, z `diagram_type`).

## Provenance (domknięcie 3-15)

Kolumny `source` (`parser`|`ocr`, VARCHAR(20)) i `confidence` (FLOAT) na
`TraceabilityMatrix` (migracja `025`) — pochodzą z `ParsedUMLModel` (diagram-level,
aplikowane na wszystkie elementy diagramu). Komponenty GUI → `source=null`
(brak podziału parser/OCR). Eksponowane w schemacie `TraceabilityEntryOut`.

## Semantyka pokrycia — Gherkin-proxy (AC4, domknięcie 3-15)

Pokrycie = element ↔ przepływ ↔ **zatwierdzony `GherkinFeature`** (`status=approved`):

- `coverage_status = covered` ↔ istnieje `linked_gherkin_id` ze zatwierdzonym feature.
- `code_reference` = nazwa zatwierdzonego feature; `code_framework = "gherkin/bdd"`.
- `test_case_id` → `null` (udokumentowane: `test_cases` wiąże się z `analysis_results`,
  nie z UML/GUI).

> **Szczere zastrzeżenie:** APPROVED Gherkin to zaakceptowana specyfikacja BDD, **nie**
> wygenerowany kod testowy (`TestCode`). Realne linkage element→TestCase→TestCode
> pozostaje follow-upem (wymagałoby nowych relacji). Udokumentowane w docstringach
> serwisu/modelu/schemy. Patrz [ADR-013](../../architecture/adr/ADR-013-traceability-proxy.md).

## Eksport (AC5, domknięcie 3-15)

`GET /projects/{id}/traceability/export?format=csv|xlsx|json|pdf`:

- **CSV** (separator `;`, UTF-8 BOM) i **JSON** — natywne.
- **XLSX** (`openpyxl`) i **PDF** (`reportlab`) — **funkcjonalne** (przeniesione do
  main deps, migracja z dev extra — uniknięcie driftu). Lazy-import + HTTP 501
  fallback zachowane jako defense-in-depth (testowane przez mock→None).

## Moduł → serwis → story

| Komponent | Serwis | Story |
|---|---|---|
| budowa macierzy | `traceability_service.py` | 3.15, 3-15 |
| eksport XLSX/PDF | `traceability_service._build_xlsx/_build_pdf` | 3.15, 3-15 |
| persystencja | `TraceabilityMatrix` (+ `source`/`confidence`) | 3-15 |

## Powiązane

- [uml-gui-data-models.md](./uml-gui-data-models.md) — `TraceabilityMatrix` + ERD.
- [ADR-013](../../architecture/adr/ADR-013-traceability-proxy.md), [ADR-010](../../architecture/adr/ADR-010-audit-logging.md).
