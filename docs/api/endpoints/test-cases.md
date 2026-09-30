# Przypadki testowe

> Plik generowany ze schemy OpenAPI przez `python -m scripts.generate_api_docs`.
> Nie edytuj ręcznie — zmiany nadpisze kolejne uruchomienie.

Zarządzanie przypadkami testowymi, generowanie kodu testowego dla wybranych frameworków, scenariusze Gherkin oraz naprawa lokatorów.

Liczba endpointów: **31**.

[↩ Powrót do spisu treści](../index.md)

---

### `POST /api/v1/projects/{project_id}/codegen/appium`

Generate Appium Route.

Launch asynchronous Appium code generation (Story 1.56).

Generuje testy mobilne Appium (``.py``, AppiumBy + Page Object Model)
z wybranych przypadków testowych. ``platform`` (opcjonalnie "android"/"ios")
wybiera desired capabilities: UiAutomator2 / XCUITest.
Mirror endpointu Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/appium' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/appium",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/appium', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/cypress`

Generate Cypress Route.

Launch asynchronous Cypress code generation from test cases (AC5).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/cypress' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/cypress",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/cypress', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/database`

Generate Database Route.

Launch asynchronous database-layer pytest code generation (Story 1.53, FR70).

Generuje izolowany kod pytest (``db_session`` + rollback) z wybranych
przypadków testowych ``test_type = database``. Mirror endpointu Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/database' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/database",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/database', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/mstest`

Generate Mstest Route.

Launch asynchronous MSTest (.NET 8) code generation (Story 1.57).

Generuje klasę ``[TestClass]`` z ``[TestMethod]`` i asercjami
``Assert.AreEqual``. Mirror endpointu Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/mstest' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/mstest",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/mstest', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/pest`

Generate Pest Route.

Launch asynchronous Pest (PHP) code generation (Story 1.55, FR24/FR12).

Generuje testy w DSL Pest (``it()``, ``expect()->toBe()``, ``toThrow``).
Mirror endpointu Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/pest' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/pest",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/pest', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/phpunit`

Generate Phpunit Route.

Launch asynchronous PHPUnit (PHP) code generation (Story 1.55, FR24/FR12).

Generuje klasę testową PHPUnit (``extends TestCase``, ``assertSame``,
``expectException``) z wybranych przypadków testowych. Mirror endpointu
Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/phpunit' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/phpunit",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/phpunit', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/playwright`

Generate Playwright Route.

Launch asynchronous Playwright code generation (Story 1.56).

Generuje spec-y Playwright (``.spec.ts``, test() + locator API) z wybranych
przypadków testowych. Mirror endpointu Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/playwright' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/playwright",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/playwright', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/selenium`

Generate Selenium Route.

Launch asynchronous Selenium code generation (Story 1.56).

Generuje testy E2E Selenium WebDriver (``.py``, Selenium 4) z wybranych
przypadków testowych. Mirror endpointu Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/selenium' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/selenium",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/selenium', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/sikulix`

Generate Sikulix Route.

Launch asynchronous SikuliX code generation from test cases (AC6).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/sikulix' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/sikulix",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/sikulix', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/testng`

Generate Testng Route.

Launch asynchronous TestNG (Java 11+) code generation (Story 1.57).

Generuje klasę z adnotacjami ``@Test``/``@BeforeMethod``
(``org.testng.annotations``) i asercjami ``Assert.assertEquals``.
Mirror endpointu Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/testng' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/testng",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/testng', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/codegen/unittest`

Generate Unittest Route.

Launch asynchronous unittest (Python) code generation (Story 1.57).

Generuje klasę ``unittest.TestCase`` (``self.assertEqual…``, uruchamialne
przez ``python -m unittest``) z wybranych przypadków testowych.
Mirror endpointu Cypress.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeGenRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/unittest' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"base_url": "przykladowa-wartosc", "framework": "cypress", "platform": "android", "test_case_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/unittest",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "base_url": "przykladowa-wartosc",
      "framework": "cypress",
      "platform": "android",
      "test_case_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/unittest', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "base_url": "przykladowa-wartosc",
    "framework": "cypress",
    "platform": "android",
    "test_case_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/codegen/{code_id}`

Get Generated Code Route.

Fetch a generated test code record with its metadata (AC5).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `code_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/3fa85f64-5717-4562-b3fc-2c963f66afa6",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/codegen/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
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

### `GET /api/v1/projects/{project_id}/gherkin`

List Gherkin Route.

Paginated list of generated Gherkin features for the project (AC-8).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `page` | query | nie |  |
| `page_size` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin', {
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

### `POST /api/v1/projects/{project_id}/gherkin/generate`

Generate Gherkin Route.

Launch asynchronous Gherkin generation from user flows (AC-1, AC-8).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `GherkinGenerateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin/generate' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"flow_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"], "feature_name": "przykladowa-wartosc"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin/generate",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "flow_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ],
      "feature_name": "przykladowa-wartosc"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin/generate', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "flow_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ],
    "feature_name": "przykladowa-wartosc"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/gherkin/{feature_id}`

Get Gherkin Route.

Gherkin feature details; ``format=raw`` returns the plain ``.feature`` text (AC-8).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `feature_id` | path | tak |  |
| `format` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin/3fa85f64-5717-4562-b3fc-2c963f66afa6",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gherkin/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
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

### `GET /api/v1/projects/{project_id}/healing/{report_id}`

Get Healing Report.

Return a healing report with its items (status, confidence, diff).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `report_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/healing/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/healing/3fa85f64-5717-4562-b3fc-2c963f66afa6",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/healing/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
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

### `POST /api/v1/projects/{project_id}/healing/{report_id}/items/{item_id}/decision`

Decide Healing Item.

Accept (apply to TestCode) or reject a proposed locator fix.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `report_id` | path | tak |  |
| `item_id` | path | tak |  |

**Ciało żądania:** `HealingDecisionRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/healing/3fa85f64-5717-4562-b3fc-2c963f66afa6/items/3fa85f64-5717-4562-b3fc-2c963f66afa6/decision' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"action": "accept"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/healing/3fa85f64-5717-4562-b3fc-2c963f66afa6/items/3fa85f64-5717-4562-b3fc-2c963f66afa6/decision",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "action": "accept"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/healing/3fa85f64-5717-4562-b3fc-2c963f66afa6/items/3fa85f64-5717-4562-b3fc-2c963f66afa6/decision', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "action": "accept"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/tests/heal`

Start Healing.

Launch an asynchronous self-healing run between two GUI versions.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `HealRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/tests/heal' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"version_a": "przykladowa-wartosc", "version_b": "przykladowa-wartosc"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/tests/heal",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "version_a": "przykladowa-wartosc",
      "version_b": "przykladowa-wartosc"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/tests/heal', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "version_a": "przykladowa-wartosc",
    "version_b": "przykladowa-wartosc"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/test-cases`

List Test Cases Route.

List test cases for the current user's tenant. Paginated.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | query | nie | Filter by project (via analysis_result.project_id) — bez tego endpoint listuje cały tenant |
| `analysis_result_id` | query | nie | Filter by analysis result |
| `source_file_id` | query | nie | Filter by source file |
| `type` | query | nie | Filter by test type |
| `status` | query | nie | Filter by status |
| `framework` | query | nie | Filter by framework |
| `priority` | query | nie | Filter by priority |
| `sort_by` | query | nie | Sort field |
| `sort_order` | query | nie | Sort order: asc|desc |
| `page` | query | nie | Page number |
| `page_size` | query | nie | Items per page |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/test-cases' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/test-cases",
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

const response = await fetch('http://localhost:8000/api/v1/test-cases', {
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

### `POST /api/v1/test-cases`

Create Test Case Route.

Create a new test case. All authenticated roles allowed.

**Uwierzytelnianie:** wymagane

**Ciało żądania:** `TestCaseCreate`

| Kod | Znaczenie |
| :-: | --- |
| `201` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/test-cases' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"analysis_result_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "title": "przykladowa-wartosc", "confidence_score": 1.0, "description": "przykladowa-wartosc", "edge_case_description": "przykladowa-wartosc", "expected_result": "przykladowa-wartosc", "framework": "przykladowa-wartosc", "generation_engine": "native"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/test-cases",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "analysis_result_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "title": "przykladowa-wartosc",
      "confidence_score": 1.0,
      "description": "przykladowa-wartosc",
      "edge_case_description": "przykladowa-wartosc",
      "expected_result": "przykladowa-wartosc",
      "framework": "przykladowa-wartosc",
      "generation_engine": "native"
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

const response = await fetch('http://localhost:8000/api/v1/test-cases', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "analysis_result_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "przykladowa-wartosc",
    "confidence_score": 1.0,
    "description": "przykladowa-wartosc",
    "edge_case_description": "przykladowa-wartosc",
    "expected_result": "przykladowa-wartosc",
    "framework": "przykladowa-wartosc",
    "generation_engine": "native"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/test-cases/bulk-delete`

Bulk Delete Test Cases Route.

Zbiorcze usuwanie test case'ów (Story 6.5, AC5).

**Uwierzytelnianie:** wymagane

**Ciało żądania:** `TestCaseBulkDeleteRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/test-cases/bulk-delete' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/test-cases/bulk-delete",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ]
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/bulk-delete', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ]
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/test-cases/bulk-update`

Bulk Update Test Cases Route.

Zbiorcza zmiana statusu/priorytetu test case'ów (Story 6.5, AC5).

**Uwierzytelnianie:** wymagane

**Ciało żądania:** `TestCaseBulkUpdateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/test-cases/bulk-update' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"], "priority": "critical", "status": "draft"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/test-cases/bulk-update",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ],
      "priority": "critical",
      "status": "draft"
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/bulk-update', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ],
    "priority": "critical",
    "status": "draft"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/test-cases/export`

Export Test Cases To Tms Route.

Eksport test case'ów do formatu TMS: TestRail CSV / Xray XML / JSON.

AC6 — puste `ids` = wszystkie test case'y tenanta; w przeciwnym razie
eksportowane są tylko wskazane (zaznaczone/przefiltrowane) rekordy.
AC7 — nazwa pliku: `testgen_{projekt}_{data}_{format}.{ext}` w nagłówku
Content-Disposition. Generowanie synchroniczne (małe pliki).

**Uwierzytelnianie:** wymagane

**Ciało żądania:** `app__schemas__tms_export__TmsExportRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/test-cases/export' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"format": "testrail", "field_mapping": {}, "ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"], "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/test-cases/export",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "format": "testrail",
      "field_mapping": {},
      "ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ],
      "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/export', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "format": "testrail",
    "field_mapping": {},
    "ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ],
    "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `DELETE /api/v1/test-cases/{test_case_id}`

Delete Test Case Route.

Delete a test case.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `test_case_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `204` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X DELETE 'http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.delete(
    "http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6",
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
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

### `GET /api/v1/test-cases/{test_case_id}`

Get Test Case Route.

Get a single test case by id.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `test_case_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6",
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
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

### `PUT /api/v1/test-cases/{test_case_id}`

Update Test Case Route.

Update test case fields. Sets is_edited=True.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `test_case_id` | path | tak |  |

**Ciało żądania:** `TestCaseUpdate`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X PUT 'http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"description": "przykladowa-wartosc", "expected_result": "przykladowa-wartosc", "framework": "przykladowa-wartosc", "imports": "przykladowa-wartosc", "metadata": {}, "preconditions": {}, "priority": "critical", "setup_code": "przykladowa-wartosc"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.put(
    "http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "description": "przykladowa-wartosc",
      "expected_result": "przykladowa-wartosc",
      "framework": "przykladowa-wartosc",
      "imports": "przykladowa-wartosc",
      "metadata": {},
      "preconditions": {},
      "priority": "critical",
      "setup_code": "przykladowa-wartosc"
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
  method: 'PUT',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "description": "przykladowa-wartosc",
    "expected_result": "przykladowa-wartosc",
    "framework": "przykladowa-wartosc",
    "imports": "przykladowa-wartosc",
    "metadata": {},
    "preconditions": {},
    "priority": "critical",
    "setup_code": "przykladowa-wartosc"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/test-cases/{test_case_id}/execute`

Execute Test Case Route.

Trigger test case execution. Returns 202 with task_id.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `test_case_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/execute' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/execute",
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/execute', {
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

### `GET /api/v1/test-cases/{test_case_id}/executions`

List Test Case Executions Route.

Get execution history for a test case.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `test_case_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/executions' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/executions",
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/executions', {
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

### `GET /api/v1/test-cases/{test_case_id}/history`

Get Test Case History Route.

Historia zmian test case'a z audit logu (Story 6.5, AC7).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `test_case_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/history' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/history",
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/history', {
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

### `POST /api/v1/test-cases/{test_case_id}/review`

Review Test Case Route.

Mark test case as reviewed by current user.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `test_case_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/review' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/review",
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/review', {
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

### `PATCH /api/v1/test-cases/{test_case_id}/status`

Update Test Case Status Route.

Update test case status (draft, ready, passed, failed, etc.).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `test_case_id` | path | tak |  |

**Ciało żądania:** `Body_update_test_case_status_route_api_v1_test_cases__test_case_id__status_patch`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X PATCH 'http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/status' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"status": "draft"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.patch(
    "http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/status",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "status": "draft"
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

const response = await fetch('http://localhost:8000/api/v1/test-cases/3fa85f64-5717-4562-b3fc-2c963f66afa6/status', {
  method: 'PATCH',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "status": "draft"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---
