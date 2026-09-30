# Pipeline DAST — autentykacja

Struktura: `AuthConfig` (`dast_runner.py`)

## 1. Obsługiwane metody

`AuthConfig.auth_type` ∈ {`form`, `token`, `basic`}. Fabryka
`AuthConfig.from_dict()` waliduje typ i ekstrahuje wymagane pola z
`credentials`.

| Metoda | Wymagane pola credentials |
|---|---|
| form | `login_url`, `username_field`, `password_field`, `username`, `password` |
| token | `token` |
| basic | `username`, `password` |

## 2. Konfiguracja w ZAP

Autentykacja konfigurowana jest przez ZAP Replacer API (wstrzykiwanie
nagłówków/wartości) zanim uruchomiony zostanie spider i active scan, dzięki
czemu skaner działa jako uwierzytelniony użytkownik i pokrywa chronione
ścieżki aplikacji.

## 3. Przykład (token)

```json
{
  "auth_type": "token",
  "credentials": { "token": "Bearer eyJ..." }
}
```

## 4. Przykład (form)

```json
{
  "auth_type": "form",
  "credentials": {
    "login_url": "https://app.example/login",
    "username_field": "email",
    "password_field": "password",
    "username": "tester@example.com",
    "password": "***"
  }
}
```

## 5. Testy kontroli dostępu

Uwierzytelniony skan umożliwia wykrywanie podatności dostępnych tylko po
zalogowaniu (np. IDOR na zasobach użytkownika). Dane uwierzytelniające nie są
zapisywane w znaleziskach — request/response są sanityzowane (nagłówki
`authorization`, `cookie`, tokeny → `[REDACTED]`).
