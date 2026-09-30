# Przykłady API — Autentykacja i MFA

Router: `app/api/routes/auth.py` (prefiks `/api/v1/auth`, tag `auth`). Tokeny:
JWT RS256 w HttpOnly cookie; nagłówek `Authorization: Bearer` dla klientów
nieprzeglądarkowych. Architektura: [ADR-003](../../adr/ADR-003-argon2id-rs256-jwt.md).

## Rejestracja

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!", "full_name": "Jan Kowalski"}'
```

`201` → weryfikacja email; konto aktywne po `/auth/verify-email`.

## Logowanie

```bash
curl -i -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}'
```

Sukces (200) ustawia ciasteczka `access_token`/`refresh_token` (HttpOnly). Gdy
użytkownik należy do >1 tenantów, zwracana jest lista do wyboru →
`/auth/select-tenant`.

**Python (httpx):**

```python
import httpx
r = httpx.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "user@example.com", "password": "SecurePass123!"},
)
client = httpx.Client(cookies=r.cookies)  # access_token w sesji
```

**JavaScript (fetch):** `credentials: "include"` przechowuje ciasteczka.

```javascript
await fetch("http://localhost:8000/api/v1/auth/login", {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "user@example.com", password: "SecurePass123!" }),
});
```

## Wybór tenanta

```bash
curl -X POST "http://localhost:8000/api/v1/auth/select-tenant" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{"tenant_id": "uuid-tenanta"}'
```

Ustawia kontekst RLS dla kolejnych zapytań ([ADR-002](../../adr/ADR-002-multi-tenancy-rls.md)).

## Odświeżanie i wylogowanie

```bash
# Refresh — używa refresh_token z cookie
curl -X POST "http://localhost:8000/api/v1/auth/refresh" -H "Cookie: access_token=…"

# Logout — unieważnia tokeny
curl -X POST "http://localhost:8000/api/v1/auth/logout" -H "Cookie: access_token=…"
```

## MFA (TOTP, opcjonalne)

```bash
# 1. Setup — zwraca secret + QR
curl -X POST "http://localhost:8000/api/v1/auth/mfa/setup" -H "Cookie: access_token=…"

# 2. Confirm — weryfikuje kod z aplikacji TOTP
curl -X POST "http://localhost:8000/api/v1/auth/mfa/confirm" \
  -H "Cookie: access_token=…" -H "Content-Type: application/json" \
  -d '{"code": "123456"}'

# 3. Verify przy logowaniu (gdy MFA aktywne)
curl -X POST "http://localhost:8000/api/v1/auth/mfa/verify" \
  -H "Content-Type: application/json" \
  -d '{"mfa_token": "...", "code": "123456"}'
```

Kody zapasowe: `POST /auth/mfa/backup-codes`. Usunięcie MFA: `DELETE /auth/mfa`.

## Typowe błędy

| Kod | Przyczyna |
|-----|-----------|
| `401` | Nieprawidłowe dane logowania / wygasły token |
| `403` | Konto zablokowane po przekroczeniu limit prób (`MAX_LOGIN_ATTEMPTS`) |
| `422` | Niepoprawne ciało (np. hasło poniżej minimalnej długości) |
