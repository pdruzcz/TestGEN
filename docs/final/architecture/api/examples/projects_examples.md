# Przykłady API — Projekty i upload dokumentacji

Router: `app/api/routes/projects.py` (prefiks `/api/v1/projects`, tag
`projects`). Wymaga autoryzacji (cookie/Bearer) i kontekstu tenanta (RLS).

## Utworzenie projektu

```bash
curl -X POST "http://localhost:8000/api/v1/projects" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{
    "name": "Platforma e-commerce",
    "description": "Testy przepływu checkout",
    "repository_url": "https://github.com/org/repo"
  }'
```

**201:**

```json
{
  "id": "uuid-projektu",
  "name": "Platforma e-commerce",
  "description": "Testy przepływu checkout",
  "repository_url": "https://github.com/org/repo",
  "status": "created",
  "created_at": "2026-06-23T10:00:00Z"
}
```

## Lista i pobranie

```bash
curl "http://localhost:8000/api/v1/projects?page=1&limit=20" -H "Cookie: access_token=…"
curl "http://localhost:8000/api/v1/projects/{project_id}" -H "Cookie: access_token=…"
```

Parametry paginacji: `page` (dom. 1), `limit` (dom. 20).

## Aktualizacja i usunięcie

```bash
curl -X PUT "http://localhost:8000/api/v1/projects/{project_id}" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{"description": "Zaktualizowany opis"}'

curl -X DELETE "http://localhost:8000/api/v1/projects/{project_id}" -H "Cookie: access_token=…"
```

`DELETE` → `204`. Usunięcie kaskadowe czyści pliki i wyniki analiz tenanta.

## Preprocessing kodu (async)

```bash
curl -X POST "http://localhost:8000/api/v1/projects/{project_id}/preprocess" \
  -H "Cookie: access_token=…"
```

`202` + `task_id`. Raport: `GET /projects/{id}/preprocessing-report`.

## Upload dokumentacji (Epic 2, async)

```bash
curl -X POST "http://localhost:8000/api/v1/projects/{project_id}/upload-documents" \
  -H "Cookie: access_token=…" \
  -F "file=@specyfikacja_wymagan.pdf" \
  -F "file_category=documentation"
```

**202** — plik ląduje w MinIO, tworzony rekord `SourceFile`, dispoczowane zadanie
`parse_document_task` (Celery). Kolejne kroki opisane w
[documents_examples.md](./documents_examples.md).

## Lista plików projektu

```bash
curl "http://localhost:8000/api/v1/projects/{project_id}/documents" -H "Cookie: access_token=…"
```

Zwraca `list[SourceFileResponse]` (status przetwarzania per plik).

## Python (httpx)

```python
import httpx
c = httpx.Client(cookies=login_cookies)
proj = c.post("http://localhost:8000/api/v1/projects",
              json={"name": "Platforma e-commerce"}).json()
c.post(f"http://localhost:8000/api/v1/projects/{proj['id']}/upload-documents",
       files={"file": open("specyfikacja.pdf", "rb")},
       data={"file_category": "documentation"})  # 202
```

## Typowe błędy

| Kod | Przyczyna |
|-----|-----------|
| `404` | Projekt nie istnieje / nie należy do tenanta |
| `409` | Konflikt (np. duplikat nazwy) |
| `422` | Niepoprawne ciało / nieobsługiwane rozszerzenie pliku |
