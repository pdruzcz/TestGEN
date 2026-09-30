# Webhooki

> Plik generowany ze schemy OpenAPI przez `python -m scripts.generate_api_docs`.
> Nie edytuj ręcznie — zmiany nadpisze kolejne uruchomienie.

Konfiguracja webhooków wychodzących TestGEN, testy połączenia i historia dostaw. Formaty zdarzeń i weryfikację podpisu opisuje [Webhooki](../webhooks.md).

Liczba endpointów: **8**.

[↩ Powrót do spisu treści](../index.md)

---

### `GET /api/v1/billing/webhooks/health`

Health webhooków płatności (panel admina).

**Story 7.3 (AC6, Task 4.3).** Liczniki przetworzonych/odrzuconych/pominiętych notyfikacji, wiek ostatniego sukcesu i seria kolejnych porażek (flaga ``alert`` przy >3 — reguła Prometheusa w README modułu). Wymaga roli **admin**.

**Uwierzytelnianie:** wymagane

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/billing/webhooks/health' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/billing/webhooks/health",
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/billing/webhooks/health', {
  method: 'GET',
  headers: {
    Authorization: `Bearer ${apiKey}`,
  },
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/billing/webhooks/tpay`

Webhook tpay (publiczny, JWS + md5sum; wszystkie typy notyfikacji).

**Story 7.4 (AC3/AC4) + 7.3 (AC2/AC5).** Macierz typów notyfikacji: transakcja (``application/x-www-form-urlencoded`` z `tr_id`, `tr_crc`, `tr_status`), aliasy BLIK (`event=ALIAS_*` + `msg_value[value]`), tokenizacja JSON (`data.token`). Autoryzacja: podpis JWS (`X-JWS-Signature`) + `md5sum` (transakcje) — bez JWT. Sukces/pomijanie → **HTTP 200** (`TRUE` / `{'result': true}`); błąd walidacji → 400 (bez ponowień); wyjątek przetwarzania → 5xx (tpay ponawia do 37 prób, idempotencja `event_uid`).

**Uwierzytelnianie:** niewymagane

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/billing/webhooks/tpay'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/billing/webhooks/tpay",
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const response = await fetch('http://localhost:8000/api/v1/billing/webhooks/tpay', {
  method: 'POST',
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/webhooks`

List Webhooks.

Webhooki firmy wraz z katalogiem dostępnych zdarzeń (AC6).

**Uwierzytelnianie:** wymagane

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/webhooks' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/webhooks",
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/webhooks', {
  method: 'GET',
  headers: {
    Authorization: `Bearer ${apiKey}`,
  },
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/webhooks`

Create Webhook.

Tworzy webhook i zapisuje sekret w postaci zaszyfrowanej (AC1).

**Uwierzytelnianie:** wymagane

**Ciało żądania:** `CreateWebhookRequest`

| Kod | Znaczenie |
| :-: | --- |
| `201` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/webhooks' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"description": "Kanał #dyzur na Slacku", "events": ["analysis.completed", "security.finding"], "secret": "zmien-mnie-na-wlasny-sekret", "url": "https://twoj-system.pl/testgen-hook"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/webhooks",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "description": "Kanał #dyzur na Slacku",
      "events": [
        "analysis.completed",
        "security.finding"
      ],
      "secret": "zmien-mnie-na-wlasny-sekret",
      "url": "https://twoj-system.pl/testgen-hook"
    },
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/webhooks', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "description": "Kanał #dyzur na Slacku",
    "events": [
      "analysis.completed",
      "security.finding"
    ],
    "secret": "zmien-mnie-na-wlasny-sekret",
    "url": "https://twoj-system.pl/testgen-hook"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `DELETE /api/v1/webhooks/{webhook_id}`

Delete Webhook.

Usuwa webhook wraz z historią dostaw (kaskada w bazie).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `webhook_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `204` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |

<details><summary>Przykład — curl</summary>

```bash
curl -X DELETE 'http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.delete(
    "http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6",
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
  method: 'DELETE',
  headers: {
    Authorization: `Bearer ${apiKey}`,
  },
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `PUT /api/v1/webhooks/{webhook_id}`

Update Webhook.

Zmienia adres, sekret, listę zdarzeń lub aktywność (AC6).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `webhook_id` | path | tak |  |

**Ciało żądania:** `UpdateWebhookRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |

<details><summary>Przykład — curl</summary>

```bash
curl -X PUT 'http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"description": "przykladowa-wartosc", "events": ["analysis.completed"], "is_active": true, "secret": "przykladowa-wartosc", "url": "przykladowa-wartosc"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.put(
    "http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "description": "przykladowa-wartosc",
      "events": [
        "analysis.completed"
      ],
      "is_active": true,
      "secret": "przykladowa-wartosc",
      "url": "przykladowa-wartosc"
    },
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
  method: 'PUT',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "description": "przykladowa-wartosc",
    "events": [
      "analysis.completed"
    ],
    "is_active": true,
    "secret": "przykladowa-wartosc",
    "url": "przykladowa-wartosc"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/webhooks/{webhook_id}/deliveries`

List Deliveries.

Historia dostaw z filtrami po statusie i typie zdarzenia (AC5).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `webhook_id` | path | tak |  |
| `limit` | query | nie |  |
| `status` | query | nie |  |
| `event_type` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6/deliveries' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6/deliveries",
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6/deliveries', {
  method: 'GET',
  headers: {
    Authorization: `Bearer ${apiKey}`,
  },
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/webhooks/{webhook_id}/test`

Test Webhook.

Wysyła testowy ping pod adres webhooka (AC1).

Wynik nie trafia do historii dostaw — to sprawdzenie konfiguracji,
nie zdarzenie biznesowe.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `webhook_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6/test' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6/test",
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/webhooks/3fa85f64-5717-4562-b3fc-2c963f66afa6/test', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
  },
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---
