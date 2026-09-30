# ADR-001: Custom monorepo (FastAPI + Angular + Flutter)

## Status

Accepted

## Kontekst

Platforma TestGEN składa się z trzech powiązanych warstw: backend (FastAPI),
frontend web (Angular) oraz klient desktop/mobile (Flutter WebView). Wymagana
jest spójna organizacja kodu, jeden potok CI/CD oraz współdzielenie kontraktu
API między warstwami. Rozproszenie kodu do osobnych repozytoriów wydłużałoby
synchronizację zmian i utrudniało atomiczne commity (zmiana endpointu +
aktualizacja klienta).

## Decyzja

Prowadzimy **własny monorepo** z trzema katalogami głównymi:

- `backend/` — FastAPI + SQLAlchemy 2.0 (async) + Celery,
- `frontend/` — Angular (standalone, Material),
- `mobile/` — Flutter WebView (klient desktop/mobile P3).

Infrastrukturę uruchamia `docker-compose.yml` (8 serwisów: backend, frontend,
celery-worker, flower, postgres, redis, rabbitmq, minio). Kontrakt API współdzielony
przez auto-generowaną specyfikację OpenAPI 3.1 z FastAPI, dostępną pod
`/openapi.json` oraz interaktywnie pod `/docs` (Swagger UI) i `/redoc`.

## Konsekwencje

**Pozytywne:**

- Jeden potok CI/CD (`make ci-lint`, `make ci-test`, `make ci-build`) dla całej
  platformy; atomiczne commity obejmujące backend + frontend.
- Spójne wersjonowanie i jedno repozytorium źródła prawdy.
- Łatwiejszy onboarding — jedna struktura katalogów do poznania.

**Negatywne:**

- Większe repozytorium; clone i historia są cięższe niż w polyrepo.
- Współdzielenie typów wymaga dyscypliny (regeneracja klienta API z OpenAPI,
  nie ręczna edycja).
- Silniejsze powiązanie zmian między zespołami backend/frontend.

## Powiązane

- [ADR-004](./ADR-004-celery-rabbitmq.md) — worker Celery w tym samym obrazie
  co backend.
- [architecture.md](../system.md) — diagram C4 kontenerów.
