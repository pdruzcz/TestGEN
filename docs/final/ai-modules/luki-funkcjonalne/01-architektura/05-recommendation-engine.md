# Recommendation engine

> Plik: `backend/app/services/gap_analysis/recommendation_engine.py`

## 1. Odpowiedzialność

`RecommendationEngine` produkuje actionable rekomendacje naprawcze dla każdej
luki w `gap_findings`. Każda rekomendacja ma:

- **priority** — P1 (natychmiast) | P2 | P3 | P4 (niski)
- **confidence** — 0.0–1.0
- **suggested_action** — konkretna akcja (np. "Dodaj funkcję `export_pdf` w
  `src/analytics/export.py`")
- **effort_estimate** — szacowany wysiłek (S / M / L)

## 2. Mapowanie priorytetów

Priorytet zależy od gap_type i severity:

| gap_type | severity | priority |
|---|---|---|
| missing | critical | **P1** |
| missing | warning | P2 |
| missing | info | P3 |
| different | critical | **P1** |
| different | warning | P2 |
| inconsistent | (zawsze critical) | **P1** |
| extra | critical | P2 |
| extra | warning | P3 |
| extra | info | P4 |

Zasada: **P1 = natychmiastowej uwagi** (missing+critical, inconsistent, different+critical).

## 3. Rekomendacje szablonowe

Rekomendacje są deterministyczne, oparte na `gap_type` i kontekście.

Przykłady szablonów:

- **missing + critical**:
  ```
  Zaimplementuj brakującą funkcjonalność: {requirement_text}.
  Sugerowana lokalizacja: nowy moduł w {file_path} lub rozszerzenie istniejącego.
  ```

- **different + warning**:
  ```
  Przejrzyj implementację '{code_entity_name}' — wymaganie ({req_id}) wskazuje
  na rozbieżność. Zweryfikuj, czy {requirement_excerpt} jest w pełni spełnione.
  ```

- **extra + warning**:
  ```
  Kod '{entity_name}' nie ma odpowiadającego wymagania w dokumentacji.
  Rozważ: (a) dodanie wymagania, (b) oznaczenie jako @internal, (c) usunięcie.
  ```

- **inconsistent**:
  ```
  Sprzeczność: kod '{entity_name}' jest mapowany do 2+ wymagań z przeciwnymi
  sygnałami ({req_ids}). Rozdziel implementację lub ujednolić wymagania.
  ```

Confidence rekomendacji: 0.7 (wynik deterministyczny, z reguł).

## 5. Szacowanie wysiłku (effort_estimate)

Prosta heurystyka:

| Warunek | Effort |
|---|---|
| missing + critical | L |
| missing + warning | M |
| missing + info | S |
| different | S |
| extra | S |
| inconsistent | M (wymaga koordynacji z PO) |

## 6. Persystencja

Rekomendacje są persystowane w `recommendations` (model
`backend/app/models/recommendation.py`) z:
- FK do `gap_findings.id`
- `priority`, `confidence`, `effort_estimate`
- `suggested_action` (Text)
- `source` (pochodzenie rekomendacji)
- `status` (open | accepted | applied | dismissed)

## 7. Endpointy API

- `GET /projects/{project_id}/recommendations` — lista z filtrami (priority,
  confidence_min, source, status)
- `POST /projects/{project_id}/recommendations/generate` — wymusza regenerację

## 8. Frontend

UI: panel "Rekomendacje" w widoku gap-analysis. Wyświetla listę z:
- priority badge (P1 czerwony, P2 pomarańczowy, P3 żółty, P4 niebieski)
- confidence jako procent + ostrzeżenie jeśli < 0.5
- suggested_action w karcie rozszerzalnej
- akcje: "Oznacz jako zaakceptowana" / "Generuj skeleton"

## 9. Testowanie

Testy jednostkowe: `backend/tests/unit/services/gap_analysis/test_recommendation_engine.py`
pokrywają template-based generowanie, mapowanie priorytetów, edge case'y
(brakujące pola).

## 10. Powiązane dokumenty

- [03 — Klasyfikator luk](03-klasyfikator-luk.md)
- [06 — Skeleton generator](06-skeleton-generator.md)
