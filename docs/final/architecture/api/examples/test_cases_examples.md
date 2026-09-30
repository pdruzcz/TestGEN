# Przykłady API — Przypadki testowe i przegląd

Router: `app/api/routes/test_cases.py` (prefiks `/api/v1/test-cases`, tag
`test-cases`). Statusy workflow: `draft` → `ready` (akceptacja) →
`passed`/`failed` (wykonanie). Architektura przeglądu:
[ADR-009](../../adr/ADR-009-code-review-workflow.md).

## Utworzenie przypadku testowego

```bash
curl -X POST "http://localhost:8000/api/v1/test-cases" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{
    "project_id": "uuid",
    "title": "Obliczenie sumy koszyka",
    "description": "Suma z pozycjami i podatkiem",
    "type": "unit",
    "priority": "high",
    "test_code": "def test_calculate_total():\n    assert calc([]) == 0"
  }'
```

**201** → `TestCaseResponse` ze statusem `draft`.

## Lista i pobranie

```bash
curl "http://localhost:8000/api/v1/test-cases?project_id={pid}&status=draft&page=1&limit=20" \
  -H "Cookie: access_token=…"
curl "http://localhost:8000/api/v1/test-cases/{test_case_id}" -H "Cookie: access_token=…"
```

Filtry: `status` (`draft`/`ready`/`passed`/`failed`), `type`
(`unit`/`integration`/`e2e`), `project_id`.

## Edycja i usunięcie

```bash
curl -X PUT "http://localhost:8000/api/v1/test-cases/{test_case_id}" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{"test_code": "def test_updated():\n    assert True", "is_edited": true}'

curl -X DELETE "http://localhost:8000/api/v1/test-cases/{test_case_id}" -H "Cookie: access_token=…"
```

`DELETE` → `204`.

## Przegląd (akceptacja)

```bash
curl -X POST "http://localhost:8000/api/v1/test-cases/{test_case_id}/review" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{"decision": "approve", "comment": "Zgodny ze standardem"}'
```

`approve` → status `ready`; `reject` → pozostaje `draft` z komentarzem. Decyzja
logowana audytowo ([ADR-010](../../adr/ADR-010-audit-logging.md)).

## Wykonanie (async)

```bash
curl -X POST "http://localhost:8000/api/v1/test-cases/{test_case_id}/execute" \
  -H "Cookie: access_token=…"
```

**202** + `task_id`. Historia wykonań:

```bash
curl "http://localhost:8000/api/v1/test-cases/{test_case_id}/executions" -H "Cookie: access_token=…"
```

Zwraca `list[TestCaseExecutionResponse]` (status, czas, logi).

## Python (httpx)

```python
import httpx
c = httpx.Client(cookies=login_cookies)
tc = c.post("http://localhost:8000/api/v1/test-cases",
            json={"project_id": pid, "title": "Suma koszyka",
                  "type": "unit", "priority": "high",
                  "test_code": "def t(): assert True"}).json()
c.post(f"http://localhost:8000/api/v1/test-cases/{tc['id']}/review",
       json={"decision": "approve"})
c.post(f"http://localhost:8000/api/v1/test-cases/{tc['id']}/execute")  # 202
```

## Typowe błędy

| Kod | Przyczyna |
|-----|-----------|
| `404` | Przypadek testowy nie istnieje |
| `409` | Akcja niedozwolona w bieżącym statusie (np. execute dla `draft`) |
| `422` | Niepoprawne ciało / nieznana decyzja review |
