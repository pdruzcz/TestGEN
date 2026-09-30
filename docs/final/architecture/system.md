# Architektura — TestGEN (P1)

Architektura warstwowa platformy. Decyzje architektoniczne:
[adr/](./adr/). Diagram C4 (uproszczony, tekstowy).

## C4 — Context

```
                ┌───────────────┐
                │   Użytkownik  │
                │ (Owner/User)  │
                └───────┬───────┘
                        │ HTTPS (JWT/cookie)
                        ▼
              ┌─────────────────────┐         ┌──────────────┐
              │     TestGEN         │◄───────►│  MinIO (S3)  │
              │  (platforma SaaS)   │         │  binaria plików │
              └─────────┬───────────┘         └──────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │   SMTP (email)      │  weryfikacja, zaproszenia, alerty
              └─────────────────────┘
```

## C4 — Container

```
┌────────────────────────────────────────────────────────────────────┐
│                         Frontend (Angular)                          │
│            standalone · Material · SPA (port 4200 → 80)             │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ REST /api/v1 (cookie JWT)
┌──────────────────────────────▼─────────────────────────────────────┐
│                         Backend (FastAPI)                           │
│   API layer · services · SQLAlchemy 2.0 async · RLS per tenant     │
│   OpenAPI 3.1 pod /openapi.json, /docs, /redoc                      │
└──────┬───────────────────────┬──────────────────────┬──────────────┘
       │                       │                      │
       ▼                       ▼                      ▼
┌─────────────┐        ┌──────────────┐       ┌──────────────────────┐
│ PostgreSQL  │        │   RabbitMQ   │       │   Celery workers     │
│  (+ RLS)    │        │  (broker)    │──────►│ kolejki: default,    │
│ dane, wyniki│        │              │       │ analysis, export,    │
└─────────────┘        └──────┬───────┘       │ security             │
                              │               └──────────┬───────────┘
                              ▼                          │
                       ┌──────────────┐                  │
                       │    Redis     │◄─────────────────┘
                       │ result bd +  │
                       │   cache      │
                       └──────────────┘

            ┌──────────────┐
            │    MinIO     │  binaria kodu/dokumentów/UML/GUI
            │  (storage)   │  (storage_key w source_files)
            └──────────────┘
```

## Warstwy backendu

- **API** (`app/api/routes/`) — endpointy FastAPI, autoryzacja JWT/cookie,
  wymuszanie RLS, walidacja Pydantic, błędy RFC 7807.
- **Serwisy** (`app/services/`) — logika domenowa: analiza dokumentacji
  (`analysis/document/`), analiza kodu (AST), generowanie testów, auth, quota,
  audyt.
- **Workery** (`app/workers/`, Celery) — zadania asynchroniczne: parsowanie
  dokumentów, analiza, czyszczenie, export, skany. Patrz [ADR-004](./adr/ADR-004-celery-rabbitmq.md).
- **Modele** (`app/models/`, SQLAlchemy 2.0 async) — PostgreSQL z RLS;
  `TenantMixin` (tenant_id), wyniki analiz w `AnalysisResult.result_data` (JSONB).

## Przepływ asynchroniczny (przykład: analiza dokumentacji)

```
POST /projects/{id}/upload-documents
  → MinIO (binaria) + SourceFile(processing)
  → parse_document_task.delay()  → 202 + task_id

Celery worker:
  → parser formatu → ParsedDocument
  → preprocessing → AnalysisResult(document_preprocessing)
  → classify / requirements / glossary / inconsistencies
  → gap_analysis / traceability / test_generation
  → SourceFile(ready)

GET /documents/{id}/status  → available_results rośnie z każdym modułem
```

Każdy moduł utrwala wynik niezależnie — częściowe wyniki dostępne przed
zakończeniem pipeline'u. Błąd jednego modułu nie blokuje pozostałych (non-fatal).

## Izolacja danych (RLS)

Każda tabela dziedziczy `tenant_id`; przed zapytaniem sesja ustawia
`app.current_tenant`. Polityki RLS wymuszają, że wiersz jest widoczny tylko dla
swojego tenanta — nawet pominięcie filtru w ORM nie ujawnia danych
([ADR-002](./adr/ADR-002-multi-tenancy-rls.md)).

## Powiązane

- [getting-started.md](../deployment-guide/getting-started.md) — uruchomienie środowiska.
- [environment-setup.md](../deployment-guide/environment-setup.md) — serwisów i porty.
- [ai/document-analysis.md](../ai-modules/analiza-dokumentacji/document-analysis.md),
  [ai/ast-analysis.md](../ai-modules/analiza-kodu/ast-analysis.md) — szczegóły modułów analizy.
