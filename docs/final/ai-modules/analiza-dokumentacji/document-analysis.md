# Analiza dokumentacji — pipeline natywny (Epic 2)

Od sparsowanego tekstu do wymagań, glosariusza, niespójności, gap analysis,
macierzy śledzenia i przypadków testowych. Wszystkie etapy oparte na regułach
(wyrażenia regularne, wzorce językowe, słowa kluczowe, słowniki) — bez modeli
zewnętrznych. Endpointy: [api/examples/documents_examples.md](../../architecture/api/examples/documents_examples.md);
formaty: [document-formats.md](./document-formats.md).

## Etapy pipeline'u

```
ParsedDocument (parser formatu)
  1. Preprocessing      → DocumentStructure (hierarchia sekcji, czyszczenie)
  2. Klasyfikacja       → ClassificationResult (typ dokumentu + pewność)
  3. Ekstrakcja wymagań → list[ExtractedRequirement]
  4. Glosariusz         → list[GlossaryTerm] (+ mapowanie na kod)
  5. Detekcja niespójności → list[Inconsistency]
  6. Gap analysis       → wymaganie vs kod projektu
  7. Traceability       → macierz śledzenia wymagań
  8. Generowanie TC     → przypadki testowe per wymaganie
```

Każdy etap utrwala wynik w `AnalysisResult(module=…, result_data=…)` (JSONB),
co umożliwia workflow i ponowną analizę bez utraty decyzji.

## Architektura asynchroniczna

Analiza jest asynchroniczna od uploadu ([ADR-004](../../architecture/adr/ADR-004-celery-rabbitmq.md)):

1. `POST /projects/{id}/upload-documents` → plik w MinIO, rekord
   `SourceFile(status=processing)` → `parse_document_task.delay()` → `202`.
2. Worker Celery pobiera binaria, parsuje, preprocessuje, następnie uruchamia
   kolejne moduły — każdy utrwala osobny `AnalysisResult`.
3. Klient odpytuje `GET /documents/{id}/status`; `available_results` rośnie z
   każdym ukończonym modułem.

Błąd w jednym module nie blokuje pozostałych (non-fatal); błąd
parsowania/preprocessingu oznacza plik `failed`.

## Klasyfikacja modułów w `AnalysisResult.module`

| `module` | Serwis | Story |
|----------|--------|-------|
| `document_preprocessing` | `DocumentPreprocessor` | 2.1–2.2 |
| `classification` | `DocumentClassifier` | 2.3 |
| `requirements` | `RequirementExtractor` | 2.4 |
| `glossary` | `GlossaryExtractor` + `TerminologyMapper` | 2.6 |
| `inconsistencies` | `InconsistencyDetector` | 2.7 |
| `gap_analysis` | `GapAnalyzer` | 2.8 |
| `traceability` | `TraceabilityMatrixGenerator` | 2.9 |
| `test_generation` | `TestGenerator` | 2.10 |

## 1. Preprocessing (`DocumentPreprocessor`)

- **Hierarchia sekcji** — drzewo parent-child wg poziomów nagłówków (stos).
- **Czyszczenie** — usuwanie numerów stron, stopek, znaków wodnych;
  de-dywizacja (łączenie słów łamanych przez `-` na końcu linii).
- **Polskie znaki** — mapowanie błędów kodowania Latin-2 → UTF-8, normalizacja NFC.
- **Brak nagłówków** — segmentacja po akapitach > 50 znaków (poziom 0);
  pusty dokument → `ValueError`, plik `failed`.

## 2. Klasyfikacja (`DocumentClassifier`)

Ocena punktowa typu dokumentu wg 4 sygnałów (wzorce tytułów ×2.0, wzorce sekcji
×1.5, słowa kluczowe ×1.0, wskaźniki struktury ×0.5) i wagi typu. Typy:
`specyfikacja_wymagań` (1.5), `podręcznik_użytkownika` (1.0),
`instrukcja_techniczna` (1.2), `opis_api` (1.3), `notatki_projektowe` (1.0),
`inny` (0.5). Pewność = `min(100, best_score/10 × 100)`.

## 3. Ekstrakcja wymagań (`RequirementExtractor`)

Zdanie staje się wymaganiem, gdy ma ID (`WYM-\d+`, `FR-\d+`, IEEE 830) LUB
pasuje do wzorca modalnego (`system musi/powinien…`) LUB należy do sekcji
wymagań. Pewność (0–100): bazowe 50 + bonusy (ID +30, sekcja +15, modalne +15,
fraza startowa +10) − kary (wzorce wykluczające, długość). Próg < 50 → pominięcie.
Typ: `functional`/`non-functional`; priorytet: `critical`/`high`/`medium`/`low`.

## 4. Glosariusz (`GlossaryExtractor` + `TerminologyMapper`)

Strategie (priorytetowo): sekcja glosariusza → wzorce definicji → częstotliwość
(akronimy/wielkie litery ≥ 3 wystąpienia). Typ terminu: `acronym`/`domain`/
`technical`/`business`. `TerminologyMapper` dopasowuje terminy do encji kodu
z analizy `logic_structures` (Epic 1) — dokładne/fuzzy, top-5 sugestii,
potwierdzane w workflow (`confirmed_mapping_ids`).

## 5. Detekcja niespójności (`InconsistencyDetector`)

| Typ | Reguła |
|-----|--------|
| `contradiction` | wzajemnie wykluczające się wzorce (critical) |
| `missing_reference` | referencja do nieistniejącego ID (high) |
| `duplicate` | podobieństwo Jaccard > 0,85 w parach tego samego typu (medium) |
| `terminology` | encja w > 2 wymaganiach pod różnymi nazwami (medium — szum) |

Status: `open` → `accepted`/`false_positive`/`fixed`.

## 6–8. Moduły zależne (tylko do odczytu)

- **Gap analysis** (`GapAnalyzer`) — wymaganie vs kod projektu:
  `implemented`/`not_implemented`/`partial`/`divergent`.
- **Traceability** (`TraceabilityMatrixGenerator`) — wymaganie → pokrycie
  (`full`/`partial`/`no`).
- **Generowanie TC** (`TestGenerator`) — szablony per typ wymagania:
  scenariusz pozytywny, negatywny, brzegowy.

> `/projects/{id}/traceability` (Epic 3) to macierz źródeł UML/GUI — odrębna od
> traceability dokumentu.

## Workflow i reparse

- **Workflow elementów** — wymagania (`extracted`/`accepted`/`rejected`/`edited`),
  niespójności, glosariusz (`is_verified`) — mutacje utrwalane w `result_data`.
- **Reparse** (`POST /documents/{id}/reparse`) — ponowna analiza bez utraty
  quoty; decyzje zachowane po mapowaniach `req_id` → `status`.

## Powiązane

- [document-formats.md](./document-formats.md) — formaty i biblioteki.
- [benchmarks.md](../analiza-kodu/benchmarks.md) — metryki baseline (golden data).
- [ADR-004](../../architecture/adr/ADR-004-celery-rabbitmq.md), [ADR-008](../../architecture/adr/ADR-008-golden-data.md).
