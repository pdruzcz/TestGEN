# Getting Started — TestGEN (P1)

Przewodnik dla nowego dewelopera: od sklonowania repo do działającego środowiska.
Cel: **< 30 minut**. Szczegóły środowiska: [environment-setup.md](./environment-setup.md);
architektura: [architecture.md](../architecture/system.md).

## Wymagania

| Narzędzie | Wersja |
|-----------|--------|
| Docker Desktop (z Compose v2) | aktualna |
| Git | aktualna |
| Python (backend lokalnie) | 3.12+ |
| Node.js (frontend lokalnie) | 22+ |
| (opcjonalnie) Flutter | 3.38 (klient P3) |

Pełne środowisko deweloperskie uruchamia **Docker Compose** — Python/Node
potrzebne tylko do pracy poza kontenerami (lint, testy natywne).

## 1. Klonowanie

```bash
git clone <repo-url> testgen
cd testgen
```

## 2. Konfiguracja `.env`

```bash
cp .env.example .env
```

Wygeneruj parę kluczy RS256 (wymagana do JWT — [ADR-003](../architecture/adr/ADR-003-argon2id-rs256-jwt.md)):

```bash
mkdir -p backend/keys
openssl genrsa -out backend/keys/private.pem 2048
openssl rsa -in backend/keys/private.pem -pubout -out backend/keys/public.pem
```

Klucz MFA (Fernet):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# wklej wynik do .env jako ENCRYPTION_KEY=
```

Opis wszystkich zmiennych: [environment-setup.md](./environment-setup.md).

## 3. Uruchomienie środowiska

```bash
make dev      # docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Uruchamia 8 serwisów: `backend`, `frontend`, `celery-worker`, `flower`,
`postgres`, `redis`, `rabbitmq`, `minio`. Skróty: `make logs`, `make down`, `make clean`.

## 4. Migracje bazy

```bash
make migrate   # alembic upgrade head (wewnątrz backend)
```

## 5. Weryfikacja

```bash
curl http://localhost:8000/api/v1/health    # → 200
# Frontend:      http://localhost:4200
# Swagger UI:    http://localhost:8000/docs
# ReDoc:         http://localhost:8000/redoc
# MinIO console: http://localhost:9001
# RabbitMQ mgmt: http://localhost:15672
```

## 6. Testy

```bash
make test          # backend: pytest
cd frontend && npx ng test     # frontend: Karma/Vitest
```

CI lustrują: `make ci-lint`, `make ci-test`, `make ci-build`.

## Pierwszy przepływ (API)

```bash
# 1. Rejestracja + logowanie (cookie access_token)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"SecurePass123!","full_name":"Dev"}'

curl -i -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"SecurePass123!"}'
# zapisz ciasteczko access_token z nagłówka Set-Cookie

# 2. Projekt + upload dokumentacji (async)
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{"name":"Demo"}'

curl -X POST http://localhost:8000/api/v1/projects/{PID}/upload-documents \
  -H "Cookie: access_token=…" -F "file=@specyfikacja.pdf" -F "file_category=documentation"
# → 202, odpytuj GET /documents/{DID}/status aż ready
```

Więcej przykładów: [api/examples/](../architecture/api/examples/).

## Rozwiązywanie problemów

| Objaw | Rozwiązanie |
|-------|-------------|
| `make dev` — port zajęty | `make down` i zwolnij port (5432/6379/5672/9000/4200/8000) |
| Health `502` po starcie | odczekaj `start_period` (backend ~15s); `make logs backend` |
| Błędy RLS w testach | test musi ustawić kontekst `app.current_tenant` |
| Migracja się cofa | `make migrate`; sprawdź `backend/alembic/versions/` |

Szczegóły: [environment-setup.md](./environment-setup.md#troubleshooting).
