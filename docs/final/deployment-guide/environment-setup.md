# Konfiguracja środowiska — TestGEN (P1)

Szczegółowy opis serwisów, portów i zmiennych środowiskowych. Szybki start:
[getting-started.md](./getting-started.md).

## Serwisy Docker Compose

`docker-compose.yml` (+ `docker-compose.dev.yml` dla dev) — 8 serwisów:

| Serwis | Obraz | Porty | Rola |
|--------|-------|-------|------|
| `backend` | budowany (`./backend`, target production) | 8000 | FastAPI API |
| `frontend` | budowany (`./frontend`) | 4200→80 | Angular SPA |
| `celery-worker` | = backend | — | worker Celery (`-Q default,analysis,export,security`) |
| `flower` | mher/flower:2.0 | 5555 | monitoring tasków Celery (basic-auth `FLOWER_USER`/`FLOWER_PASSWORD`) |
| `postgres` | postgres:16-alpine | 5432 | baza + RLS |
| `redis` | redis:7-alpine | 6379 | result backend Celery + cache |
| `rabbitmq` | rabbitmq:3.12-management-alpine | 5672, 15672 | broker zadań |
| `minio` | minio/minio | 9000, 9001 | storage S3 binariów |

Wolumeny: `postgres-data`, `redis-data`, `rabbitmq-data`, `minio-data`.

## OS-specific

- **Windows**: Docker Desktop z WSL2; skrypty używają POSIX — używaj Git Bash
  lub WSL. Ścieżki kluczy w `.env` z ukośnikami w przód (`keys/private.pem`).
- **macOS**: Docker Desktop; colima jako alternatywa.
- **Linux**: Docker Engine + Compose v2 (natively).

## Zmienne środowiskowe (`.env`)

Wszystkie z domyślnymi wartościami w `.env.example`. Skopiuj: `cp .env.example .env`.

### Aplikacja / backend

| Zmienna | Opis |
|---------|------|
| `APP_NAME`, `APP_ENV`, `DEBUG` | nazwa, środowisko, tryb debug |
| `BACKEND_HOST`, `BACKEND_PORT` | bind serwera (0.0.0.0:8000) |
| `SECRET_KEY` | sekret aplikacji (zmień w produkcji) |

### JWT (RS256)

| Zmienna | Opis |
|---------|------|
| `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH` | ścieżki kluczy PEM ([ADR-003](../architecture/adr/ADR-003-argon2id-rs256-jwt.md)) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | TTL access tokenu (15) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | TTL refresh tokenu (7) |

### Baza danych (PostgreSQL)

| Zmienna | Opis |
|---------|------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` | parametry PG |
| `DATABASE_URL` | `postgresql+asyncpg://…` |

### Redis / RabbitMQ / MinIO

| Zmienna | Opis |
|---------|------|
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_URL` | cache + result backend |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD`, `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_URL` | broker |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ENDPOINT`, `MINIO_USE_SSL` | storage |

### Celery

| Zmienna | Opis |
|---------|------|
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | broker (amqp) + backend (redis) |
| `CELERY_SOFT_TIME_LIMIT`, `CELERY_HARD_TIME_LIMIT` | limity czasu (300/330) |
| `CELERY_MAX_RETRIES`, `CELERY_RETRY_DELAYS` | ponowienia (3; 10/60/300 s) |

### Auth: MFA, ciasteczka, brute-force

| Zmienna | Opis |
|---------|------|
| `MFA_TOKEN_EXPIRE_MINUTES`, `ENCRYPTION_KEY` | TOTP + Fernet dla sekretów MFA |
| `COOKIE_SECURE`, `COOKIE_DOMAIN` | flagi HttpOnly cookie |
| `MAX_LOGIN_ATTEMPTS`, `ACCOUNT_LOCKOUT_MINUTES`, `LOGIN_ATTEMPTS_WINDOW_MINUTES` | blokada po nieudanych próbach |

### SMTP / email / CORS / admin

| Zmienna | Opis |
|---------|------|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS` | wysyłka email |
| `EMAIL_VERIFICATION_URL_TEMPLATE`, `EMAIL_INVITATION_URL_TEMPLATE` | szablony linków |
| `CORS_ORIGINS` | dozwolone originy (dev: `localhost:4200,localhost:8000`) |
| `BOOTSTRAP_ADMIN`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | bootstrap platform admina (`__system__`) |
| `API_URL` | bazowy URL API dla frontendu |

## <a id="troubleshooting"></a>Troubleshooting

| Problem | Rozwiązanie |
|---------|-------------|
| Backend nie wstaje | `make logs backend`; sprawdź `DATABASE_URL`, obecność kluczy RSA |
| `celery-worker` nie pobiera zadań | sprawdź `RABBITMQ_URL`; `make celery-inspect` |
| MFA setup rzuca błąd | ustaw `ENCRYPTION_KEY` (Fernet) |
| RLS blokuje wszystko | kontekst `app.current_tenant` ustawiany po `/auth/select-tenant` |
| MinIO `connection refused` | odczekaj healthcheck; sprawdź `MINIO_ENDPOINT` |
| Porty zajęte | `make down`; zwolnij 5432/6379/5672/9000/4200/8000 |
| Migracje się nie aplikują | `make migrate`; sprawdź `backend/alembic/versions/` |

## Powiązane

- [getting-started.md](./getting-started.md), [architecture.md](../architecture/system.md).
- [ADR-002](../architecture/adr/ADR-002-multi-tenancy-rls.md), [ADR-003](../architecture/adr/ADR-003-argon2id-rs256-jwt.md),
  [ADR-004](../architecture/adr/ADR-004-celery-rabbitmq.md).
