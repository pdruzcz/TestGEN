# Przegląd API — platforma TestGEN (P1)

Autorytatywna specyfikacja maszyny to **OpenAPI 3.1**, generowana z FastAPI i
dostępna na trzy sposoby:

- `GET /openapi.json` — surowy schemat (JSON),
- `/docs` — Swagger UI (interaktywny, „Try it out"),
- `/redoc` — ReDoc (czytelna referencja).

Treść tego katalogu jest **przeglądem i przykładami**; przy rozbieżności
zawsze decyduje `/openapi.json`. Endpointy opisane są w języku polskim
(`summary`, `description`), terminy techniczne pozostają w oryginale.

## Konwencje

- **Prefiks:** wszystkie ścieżki pod `/api/v1`.
- **Bazowy URL (dev):** `http://localhost:8000`.
- **Content-Type:** `application/json` (poza uploadem — `multipart/form-data`).
- **Identyfikatory:** UUID.

### Uwierzytelnianie

JWT (RS256) w **HttpOnly cookie** (`access_token`, `refresh_token`) z flagami
`Secure`/`SameSite`. Klienci nieprzeglądarkowe (CLI, SDK) mogą używać nagłówka
`Authorization: Bearer <token>`. Szczegóły: [ADR-003](../adr/ADR-003-argon2id-rs256-jwt.md),
przykłady: [auth_examples.md](./examples/auth_examples.md).

### Przetwarzanie asynchroniczne

Operacje czasochłonne (analiza kodu, analiza dokumentacji, wykonywanie testów)
zwracają natychmiast **`202 Accepted`** z identyfikatorem zadania:

```json
{ "task_id": "uuid", "status": "pending", "status_url": "/api/v1/tasks/{task_id}" }
```

Status odpytujemy przez `GET /tasks/{task_id}` lub dedykowany endpoint
(`GET /documents/{id}/status`). Architektura asynchroniczna:
[ADR-004](../adr/ADR-004-celery-rabbitmq.md).

### Błędy

Błędy walidacji ciała zwracane są jako **RFC 7807** `application/problem+json`
(HTTP `422`). Standardowe kody HTTP: `400`, `401`, `403`, `404`, `409`, `422`,
`429`. Przykład:

```json
{
  "type": "about:blank",
  "title": "Validation Error",
  "status": 422,
  "detail": "Pole 'name' jest wymagane.",
  "instance": "/api/v1/projects"
}
```

### Multi-tenancy i RLS

Każde zapytanie wykonuje się w kontekście tenanta ustawionym w sesji
(`app.current_tenant`); polityki RLS wymuszają izolację danych
([ADR-002](../adr/ADR-002-multi-tenancy-rls.md)). Wybór tenanta następuje po
logowaniu (`/auth/select-tenant`).

## Mapa domen (P1 = Epic 1 + Epic 2)

| Domena | Router | Przykłady |
|--------|--------|-----------|
| Autentykacja i MFA | `auth.py` (`/auth`) | [auth_examples.md](./examples/auth_examples.md) |
| Projekty, członkowie, upload dokumentacji | `projects.py` (`/projects`) | [projects_examples.md](./examples/projects_examples.md) |
| Upload i analiza kodu (AST) | `uploads.py`, `analysis.py` | [analysis_examples.md](./examples/analysis_examples.md) |
| Przypadki testowe i przegląd | `test_cases.py` (`/test-cases`) | [test_cases_examples.md](./examples/test_cases_examples.md) |
| Analiza dokumentacji (Epic 2) | `documents.py` (`/documents`) | [documents_examples.md](./examples/documents_examples.md) |
| Logi audytowe (admin) | model `AuditLog` + serwis audytu | [audit_examples.md](./examples/audit_examples.md) |

Endpointy Epic 3 (UML/GUI, Gherkin, traceability źródeł) i Epic 4 (skany
bezpieczeństwa, CVE) są poza zakresem P1 — patrz `/openapi.json`.
