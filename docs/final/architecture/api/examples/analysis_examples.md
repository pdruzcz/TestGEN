# Przykłady API — Upload i analiza kodu (AST)

Routery: `app/api/routes/uploads.py` (przesyłanie kodu) oraz
`app/api/routes/analysis.py` (analiza AST, tag `analysis`). Analiza jest
asynchroniczna ([ADR-004](../../adr/ADR-004-celery-rabbitmq.md)); parser AST to
tree-sitter ([ADR-005](../../adr/ADR-005-tree-sitter-parser.md)). Opis mechaniki:
[ai/ast-analysis.md](../../../ai-modules/analiza-kodu/ast-analysis.md).

## Upload kodu źródłowego

```bash
curl -X POST "http://localhost:8000/api/v1/projects/{project_id}/upload" \
  -H "Cookie: access_token=…" \
  -F "file=@app.zip"
```

`202` + `task_id`. Obsługiwane: pojedyncze pliki oraz archiwa `.zip`. Język
wykrywany automatycznie; opcjonalnie można go wymusić.

> Pełna lista obsługiwanych języków i parametrów: `/openapi.json` (tag
> `uploads`).

## Uruchomienie analizy (async)

```bash
curl -X POST "http://localhost:8000/api/v1/projects/{project_id}/analysis" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{}'
```

**202:**

```json
{ "task_id": "uuid", "status": "pending", "status_url": "/api/v1/tasks/{task_id}" }
```

## Status i wyniki

```bash
curl "http://localhost:8000/api/v1/tasks/{task_id}" -H "Cookie: access_token=…"
curl "http://localhost:8000/api/v1/projects/{project_id}/analysis" -H "Cookie: access_token=…"
```

Wynik analizy (`logic_structures`) zawiera wykryte funkcje, klasy, importy,
parametry i typy zwracane — utrwalone w `AnalysisResult.result_data` (JSONB).

**Przykładowy fragment wyniku:**

```json
{
  "functions": [
    {
      "name": "calculate_total",
      "file_path": "app/cart.py",
      "line_start": 15,
      "line_end": 25,
      "parameters": ["items", "tax_rate"],
      "return_type": "float"
    }
  ],
  "classes": [],
  "imports": []
}
```

## Python (httpx)

```python
import httpx
c = httpx.Client(cookies=login_cookies)
c.post(f"http://localhost:8000/api/v1/projects/{pid}/upload",
       files={"file": open("app.zip", "rb")})            # 202
c.post(f"http://localhost:8000/api/v1/projects/{pid}/analysis")  # 202 + task_id
# odpytywanie /tasks/{task_id} aż status=completed, potem /analysis
```

## Typowe błędy

| Kod | Przyczyna |
|-----|-----------|
| `202` | Zadanie przyjęte / wynik jeszcze niedostępny (odpytaj `/status`) |
| `404` | Projekt/plik nie istnieje |
| `422` | Nieobsługiwany format archiwum |
