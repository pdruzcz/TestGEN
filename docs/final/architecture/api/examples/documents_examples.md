# Przykłady API — Analiza dokumentacji (Epic 2)

Router: `app/api/routes/documents.py` (prefiks `/api/v1/documents`, tag
`documents`). Autoryzacja JWT/cookie; izolacja RLS per tenant. Cały pipeline
natywny (regułowy) — tryb silnika pochodzi z konfiguracji i nie jest parametrem
żądania. Architektura: [ADR-004](../../adr/ADR-004-celery-rabbitmq.md),
opis pipeline'u: [ai/document-analysis.md](../../../ai-modules/analiza-dokumentacji/document-analysis.md).

## 1. Upload (async) — przez `/projects/{id}/upload-documents`

```bash
curl -X POST "http://localhost:8000/api/v1/projects/{project_id}/upload-documents" \
  -H "Cookie: access_token=…" \
  -F "file=@specyfikacja_wymagan.pdf" \
  -F "file_category=documentation"
```

**202** — plik do MinIO, rekord `SourceFile`, dispoczowane `parse_document_task`:

```json
{ "source_file_id": "a1b2…", "task_id": "e5f6…", "status": "pending",
  "status_url": "/api/v1/tasks/e5f6…" }
```

`document_id` = `source_file_id` w kolejnych wywołaniach.

## 2. Status analizy

```bash
curl "http://localhost:8000/api/v1/documents/{document_id}/status" -H "Cookie: access_token=…"
```

```json
{
  "document_id": "a1b2…", "status": "ready", "progress": 80.0,
  "available_results": ["document_preprocessing", "classification", "requirements", "glossary"],
  "error": null
}
```

`status`: `uploaded` | `processing` | `ready` | `failed`.

## 3. Pełny wynik analizy

```bash
curl "http://localhost:8000/api/v1/documents/{document_id}/analysis" -H "Cookie: access_token=…"
```

```json
{
  "document_id": "a1b2…", "filename": "specyfikacja_wymagan.pdf",
  "classification": { "doc_type": "specyfikacja_wymagań", "confidence": 100.0 },
  "requirements": [ { "req_id": "WYM-001", "text": "System musi…",
                      "type": "functional", "priority": "critical", "status": "extracted" } ],
  "glossary": [ { "term": "MFA", "definition": "…", "term_type": "acronym" } ],
  "inconsistencies": [ { "type": "duplicate", "severity": "medium", "status": "open" } ],
  "gap_analysis": { "total_requirements": 7, "implemented": 4, "coverage_percentage": 57.1 },
  "traceability": { "total_requirements": 7, "full_coverage": 4, "coverage_percentage": 57.1 },
  "test_generation": { "total_requirements": 7, "generated_tests": 12 }
}
```

`202` gdy preprocessing jeszcze trwa.

## 4. Wymagania + workflow

```bash
# Lista
curl "http://localhost:8000/api/v1/documents/{document_id}/requirements" -H "Cookie: access_token=…"

# Akceptacja / odrzucenie
curl -X POST "http://localhost:8000/api/v1/documents/{document_id}/requirements/WYM-001/accept" \
  -H "Cookie: access_token=…"
curl -X POST "http://localhost:8000/api/v1/documents/{document_id}/requirements/WYM-001/reject" \
  -H "Cookie: access_token=…"

# Edycja
curl -X PUT "http://localhost:8000/api/v1/documents/{document_id}/requirements/WYM-001" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{"text": "System musi umożliwiać logowanie email i hasła oraz MFA.", "priority": "critical"}'
```

Status workflow: `extracted` | `accepted` | `rejected` | `edited`.

## 5. Klasyfikacja, sekcje, glosariusz, niespójności

```bash
curl -X POST "http://localhost:8000/api/v1/documents/{document_id}/classify" -H "Cookie: access_token=…"
curl "http://localhost:8000/api/v1/documents/{document_id}/classification" -H "Cookie: access_token=…"
curl "http://localhost:8000/api/v1/documents/{document_id}/sections" -H "Cookie: access_token=…"
curl "http://localhost:8000/api/v1/documents/{document_id}/glossary" -H "Cookie: access_token=…"
curl "http://localhost:8000/api/v1/documents/{document_id}/inconsistencies" -H "Cookie: access_token=…"
```

Mapowanie glosariusza na kod (Epic 1): `POST /documents/{id}/glossary/map-to-code`.
Oznaczanie niespójności: `PUT /documents/{id}/inconsistencies/{inconsistency_id}`
(`status`: `open` | `accepted` | `false_positive` | `fixed`).

## 6. Ponowna analiza (reparse)

```bash
curl -X POST "http://localhost:8000/api/v1/documents/{document_id}/reparse" -H "Cookie: access_token=…"
```

`202` — ponowne parsowanie/ekstrakcja bez utraty quoty; decyzje workflow
zachowane po mapowaniach `req_id` → `status`.

## Moduły zależne (tylko do odczytu)

`gap_analysis`, `traceability`, `test_generation` nie mają osobnych endpointów
CRUD — zwracane jako klucze w `GET /documents/{id}/analysis` (pkt 3).

> `/projects/{project_id}/traceability` (Epic 3) to macierz śledzenia źródeł
> UML/GUI — odrębna funkcjonalność, poza zakresem P1.

## Typowe błędy

| Kod | Przyczyna |
|-----|-----------|
| `202` | Wynik jeszcze niedostępny (preprocessing trwa) — odpytaj `/status` |
| `404` | Dokument / wymaganie / sekcja nie istnieje |
| `422` | Niepoprawne ciało / wartość spoza zbioru (np. status niespójności) |
