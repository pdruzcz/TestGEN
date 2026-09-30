# ADR-004: Celery + RabbitMQ (przetwarzanie asynchroniczne)

## Status

Accepted

## Kontekst

Analiza kodu (AST, drzewa zależności) i analizy dokumentacji/UML/GUI są
wieloetapowe i czasochłonne (parsowanie, preprocessing, ekstrakcja). Wykonywanie
ich synchronicznie w żądaniu HTTP blokowałoby worker uvicorn i przekraczało
limity czasowe klienta. Potrzebny jest niezawodny broker zadań z kolejkami
tematycznymi, ponawianiem i możliwością monitorowania.

## Decyzja

- **Broker zadań:** Celery z **RabbitMQ** jako brokerem oraz **Redisem** jako
  result backend (`CELERY_RESULT_BACKEND=redis://...`).
- **Kolejki tematyczne:** `default`, `analysis`, `export`, `security`
  (worker uruchamiany z `-Q default,analysis,export,security`).
- **Pipeline per moduł analizy:** każda analiza (np.
  `parse_document_task`) to zadanie Celery; wyniki etapów utrwalane są
  niezależnie w `AnalysisResult.result_data` (JSONB), dzięki czemu częściowe
  wyniki są dostępne jeszcze przed zakończeniem całego pipeline'u.
- **Limity:** `CELERY_SOFT_TIME_LIMIT=300`, `CELERY_HARD_TIME_LIMIT=330`,
  `CELERY_MAX_RETRIES=3` z rosnącymi opóźnieniami.
- **Monitorowanie:** Flower (UI tasków Celery, port 5555) — wdrożony jako
  **usługa produkcyjna** w `docker-compose.yml` (obraz `mher/flower:2.0`,
  `depends_on: rabbitmq`, healthcheck TCP), chroniona basic-auth przez
  `FLOWER_USER`/`FLOWER_PASSWORD`. Lokalnie dostępna też przez `make celery-flower`.
  UWAGA: Flower wystawia argumenty zadań — bez basic-auth (fallback
  `flower_dev_password`) nie uruchamiać na serwerze dostępnym w sieci.

## Konsekwencje

**Pozytywne:**

- Endpointy uploadu zwracają natychmiast `202` + `task_id`; klient odpytuje
  status — żaden request HTTP nie czeka na pełną analizę.
- Błąd jednego modułu nie blokuje pozostałych (non-fatal); parsowanie/preprocessing
  jako jedyne oznaczają plik `failed`.
- RabbitMQ to dojrzały standard; dobre wsparcie w ekosystemie Python.

**Negatywne:**

- Większa powierzchnia operacyjna: dodatkowe serwisy (rabbitmq, redis,
  celery-worker, flower) w `docker-compose`; Flower wymaga basic-auth i
  otwarcia portu 5555 na firewallu.
- Debugowanie zadań asynchronicznych jest trudniejsze niż kodu synchronicznego.
- Wymaga zarządzania idempotentnością zadań (reparse, ponowienia).

## Powiązane

- [ADR-001](./ADR-001-custom-monorepo.md) — celery-worker w tym samym obrazie
  co backend (`target: production`).
- [architecture.md](../system.md) — diagram przepływu asynchronicznego.
- [environment-setup.md](../../deployment-guide/environment-setup.md) — zmienne `CELERY_*`,
  `RABBITMQ_*`.
