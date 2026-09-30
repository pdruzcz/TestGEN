# ADR-013: Traceability — semantyka Gherkin-proxy + provenance `source`/`confidence`

## Status

Accepted

## Kontekst

Macierz śledzenia (3.15) łączy elementy źródłowe UML/GUI z testami i pokryciem.
Dwa problemy (domknięcie 3-15):

1. **Asymetria tokenów post-3-1b.** `_element_type` czytało `element_type`/`type`,
   nie `element_kind` — klasa z OCR (`element_type="class"`) → `"class"`, ale ta sama
   klasa z XMI (`element_kind="class"`) → `"element"`. Po fixie 3-1b (visual emituje
   `element_kind`) asymetria nie znikała bez zmiany w traceability.
2. **Data-model gap.** Story zakładała linkage element→TestCase→TestCode
   (`source_flow_id`/`GeneratedTestCode`), które nie istniały. Pokrycie było proxy:
   COVERED = APPROVED `GherkinFeature` traktowane jako „kod wygenerowany" —
   semanticznie błędne (Gherkin ≠ kod testowy). `test_case_id` zawsze null.

## Decyzja

1. **`_element_type` czyta `element_kind` pierwsze** (kanoniczny dyskryminator
   strukturalny), potem `element_type`/`type`; mapa `_UML_TYPE_MAP` uzupełniona o
   tokeny wizualne (`decision`→activity, `enum`→class; `node` dwuznaczny → parametr
   `category` z `diagram_type`).
2. **Provenance:** kolumny `source` (`parser`|`ocr`) + `confidence` (FLOAT) na
   `TraceabilityMatrix` (migracja `025`), eksponowane w `TraceabilityEntryOut`.
3. **Semantyka proxy — uczciwie udokumentowana** (decyzja usera: dokumentuj, nie
   implementuj nowych relacji): COVERED = APPROVED Gherkin = zaakceptowana
   specyfikacja BDD, **nie** wygenerowany kod testowy; `test_case_id` null z
   udokumentowanym powodem (`test_cases` wiąże się z `analysis_results`). Realne
   linkage element→TestCase→TestCode = follow-up.

## Konsekwencje

**Pozytywne:**

- Spójne typy elementów niezależnie od źródła (OCR vs parser) — koniec asymetrii.
- Provenance pozwala odróżnić elementy z OCR (niższa wierność) w macierzy.
- Szczera semantyka pokrycia (bez udawania, że Gherkin = kod).

**Negatywne:**

- `test_case_id` pozostaje null do czasu realnego linkage'u (follow-up).
- Mapowanie `node` wymaga kontekstu `diagram_type` (parametr `category`).

## Powiązane

- [ai/traceability-uml-gui.md](../../ai-modules/analiza-uml-gui/traceability-uml-gui.md) — macierz + eksport.
- [ADR-011](./ADR-011-uml-visual-tier2.md) — `element_kind` z OCR.
- Domknięcie `3-15` (`_bmad-output/implementation-artifacts/E3/3-15-domkniecie.md`).
