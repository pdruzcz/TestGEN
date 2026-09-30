# Przykłady API — moduł UML/GUI (Epic 3)

Przykłady wywołań endpointów modułu UML/GUI. Autorytatywna specyfikacja maszynowa:
`/openapi.json`, `/docs` (Swagger), `/redoc`. Tagi: `uml`, `gui`, `gherkin`,
`codegen`, `test-cases`, `traceability`. Modele:
[ai/uml-gui-data-models.md](../../../ai-modules/analiza-uml-gui/uml-gui-data-models.md).

## Autoryzacja

Wszystkie endpointy wymagają uwierzytelnienia: **Bearer JWT**
(`Authorization: Bearer <token>`) lub cookie sesyjne (`/api/v1/auth/login`).
Zależność `get_current_user` aktywuje **RLS** (`SET LOCAL app.current_tenant`).
Bazowy prefiks: `/api/v1`.

## Kody statusu

| Kod | Znaczenie |
|---|---|
| 200 | OK — zwrócono zasób |
| 202 | Accepted — zadanie asynchroniczne (Celery) przyjęte, zwraca `task_id` |
| 400 | Błąd żądania (puste dane wejściowe, brak kontekstu org) |
| 401/403 | Brak tokena / brak uprawnień (RBAC/RLS) |
| 404 | Zasób nie istnieje |
| 422 | Błąd walidacji (Pydantic/Query) |
| 500 | Błąd serwera |
| 501 | Funkcja niedostępna (np. eksport XLSX/PDF bez biblioteki) |

## UML (Stories 3.1–3.7)

```bash
# Wgranie diagramu (PlantUML/XMI/SVG/PDF/PNG)
curl -X POST "$API/projects/$PID/uml/upload" \
  -H "Authorization: Bearer $TOKEN" -F "file=@diagram.puml"

# Parsowanie → parsed_uml_models
curl -X POST "$API/projects/$PID/uml/parse" -H "Authorization: Bearer $TOKEN"

# Cross-diagram → user flows (asynchronicznie)
curl -X POST "$API/projects/$PID/uml/analyze" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"diagram_ids": null}'
# 202 → {"task_id": "…", "status": "pending"}

# Porównanie diagramu klas z kodem projektu (compare-code)
curl -X POST "$API/projects/$PID/uml/$DID/compare-code" \
  -H "Authorization: Bearer $TOKEN"
```

Lista/zasoby: `GET /projects/{id}/uml`, `GET /projects/{id}/uml/{diagram_id}`,
`GET /projects/{id}/uml/flows`, `GET /projects/{id}/uml/flows/{flow_id}`.

## GUI (Stories 3.8–3.10)

```bash
# Wgranie screenshotu (≤ 20 MB; PNG/JPG/JPEG/BMP/TIFF/WebP)
curl -X POST "$API/projects/$PID/gui/upload" \
  -H "Authorization: Bearer $TOKEN" -F "file=@ekran.png"

# Analiza CV/OCR (asynchronicznie) → gui_components + layout
curl -X POST "$API/projects/$PID/gui/analyze" -H "Authorization: Bearer $TOKEN"

# Regresja wizualna (porównanie dwóch screenshotów, Story 3.10)
curl -X POST "$API/projects/$PID/gui/compare" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"baseline_screenshot_id": "…", "comparison_screenshot_id": "…"}'
```

Zasoby: `GET /projects/{id}/gui/{screenshot_id}/result`, `GET/POST /projects/{id}/gui/flows`,
`GET /projects/{id}/gui/comparisons`, `GET /projects/{id}/gui/comparisons/{id}/diff`.

## Gherkin / BDD (Story 3.11)

```bash
# Generowanie scenariuszy z przepływów (asynchronicznie)
curl -X POST "$API/projects/$PID/gherkin/generate" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"flow_ids": ["…"], "feature_name": "Logowanie"}'
# 400, gdy flow_ids puste
```

Zasoby: `GET /projects/{id}/gherkin` (paginacja),
`GET /projects/{id}/gherkin/{feature_id}` (`?format=raw` → tekst `.feature`).

## Codegen (Stories 3.12, 3.13)

```bash
curl -X POST "$API/projects/$PID/codegen/cypress" -H "Authorization: Bearer $TOKEN"
curl -X POST "$API/projects/$PID/codegen/sikulix" -H "Authorization: Bearer $TOKEN"
curl "$API/projects/$PID/codegen/$CODE_ID" -H "Authorization: Bearer $TOKEN"
```

`GET /codegen/{code_id}` zwraca opcjonalne `pattern_images` (`[{name, storage_key, component_id}]`)
dla SikuliX — realnie wyprodukowane PNG (zob. [ai/gui-analysis.md](../../../ai-modules/analiza-uml-gui/gui-analysis.md)).

## Traceability (Story 3.15)

```bash
# Macierz + summary (filtry: source_type, coverage_status, paginacja)
curl "$API/projects/$PID/traceability?source_type=uml&page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# Przebudowa (asynchronicznie)
curl -X POST "$API/projects/$PID/traceability/build" -H "Authorization: Bearer $TOKEN"

# Eksport (csv|xlsx|json|pdf)
curl -L "$API/projects/$PID/traceability/export?format=csv" \
  -H "Authorization: Bearer $TOKEN" -o traceability.csv
```

XLSX/PDF funkcjonalne (openpyxl/reportlab w main deps); lazy-import + 501 fallback
jako defense-in-depth. Odpowiedź `TraceabilityMatrixOut`:
[ai/uml-gui-data-models.md](../../../ai-modules/analiza-uml-gui/uml-gui-data-models.md).

## Sekwencje wywołań

```
UML:        upload → parse → analyze → gherkin/generate → codegen/cypress
GUI:        gui/upload → gui/analyze → gui/flows → codegen/sikulix
Regresja:   gui/upload (baseline) → gui/upload (comparison) → gui/compare
Traceability: traceability/build → traceability (GET) → traceability/export
```

## Powiązania ze Stories

| Endpoint(y) | Story |
|---|---|
| `/uml/upload`, `/uml/parse` | 3.1–3.6 |
| `/uml/analyze`, `/uml/flows`, `/uml/{id}/compare-code` | 3.7, 3.4 |
| `/gui/upload`, `/gui/analyze`, `/gui/{id}/result` | 3.8 |
| `/gui/flows`, `/gui/compare`, `/gui/comparisons` | 3.9, 3.10 |
| `/gherkin/*` | 3.11 |
| `/codegen/cypress`, `/codegen/sikulix` | 3.12, 3.13 |
| `/traceability/*` | 3.15 |
