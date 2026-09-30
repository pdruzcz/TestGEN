# Luki funkcjonalne i zgodność

> Plik generowany ze schemy OpenAPI przez `python -m scripts.generate_api_docs`.
> Nie edytuj ręcznie — zmiany nadpisze kolejne uruchomienie.

Porównanie dokumentacji z kodem, luki funkcjonalne, rekomendacje oraz macierz śledzenia wymaganie → kod → test.

Liczba endpointów: **24**.

[↩ Powrót do spisu treści](../index.md)

---

### `GET /api/v1/projects/{project_id}/code-errors`

List Code Errors.

List code errors with filters and pagination.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `category` | query | nie |  |
| `severity` | query | nie |  |
| `page` | query | nie |  |
| `size` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors', {
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

### `POST /api/v1/projects/{project_id}/code-errors/scan`

Start Code Error Scan.

Launch asynchronous code error detection for the project.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CodeErrorScanRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/scan' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"categories": ["syntax"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/scan",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "categories": [
        "syntax"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/scan', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "categories": [
      "syntax"
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

### `GET /api/v1/projects/{project_id}/code-errors/summary`

Get Code Error Summary.

Get summary of code errors for the project.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/summary' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/summary",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/summary', {
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

### `PATCH /api/v1/projects/{project_id}/code-errors/{error_id}/status`

Update Code Error Status.

Triage a code error (dismiss as false_positive — Story 5.10, AC4).

Dismissed findings stay out of lists/summaries and are not re-detected
on rescans of the same code state (stable fingerprint key).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `error_id` | path | tak |  |

**Ciało żądania:** `CodeErrorStatusUpdateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X PATCH 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/3fa85f64-5717-4562-b3fc-2c963f66afa6/status' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"status": "open"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.patch(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/3fa85f64-5717-4562-b3fc-2c963f66afa6/status",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "status": "open"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/code-errors/3fa85f64-5717-4562-b3fc-2c963f66afa6/status', {
  method: 'PATCH',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "status": "open"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/compliance`

Get Compliance Score.

**Compliance score projektu (Epic 5, FR40).**

Score 0-100, gdzie 100 = pełna zgodność z dokumentacją. Obliczane w locie z `gap_findings` na podstawie penalty weights:
- missing+critical = 15, missing+warning = 8, missing+info = 3
- different+critical = 10, different+warning = 5, different+info = 2
- inconsistent = 10/5/2
- extra = 5/3/1

Wzór: `score = max(0, 100 - Σ penalties)`.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Score projektu |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance', {
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

### `GET /api/v1/projects/{project_id}/compliance/compare`

Compare Versions.

**Porównanie dwóch snapshotów compliance (Story 5.7).**

Parametry `v1` i `v2` to IDs snapshotów. Zwraca per-finding diff:
- `fixed` — luki rozwiązane między wersjami
- `new` — luki dodane od v1
- `unchanged` — bez zmian
- `worsened` — score się obniżył

Plus delta compliance i trend.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `v1` | query | tak | First snapshot ID |
| `v2` | query | tak | Second snapshot ID |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/compare' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/compare",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/compare', {
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

### `POST /api/v1/projects/{project_id}/compliance/export`

Export Compliance Report.

Export full compliance report as CSV string.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/export' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/export",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/export', {
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

### `GET /api/v1/projects/{project_id}/compliance/functions`

Get Compliance Functions.

**Compliance score per funkcja / byt kodu.**

Grupuje findings po `code_entity_id` i wylicza score 0-100 per funkcja. Użyteczne do drill-down w module.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/functions' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/functions",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/functions', {
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

### `GET /api/v1/projects/{project_id}/compliance/modules`

Get Compliance Modules.

**Compliance score per moduł (plik).**

Grupuje findings po `file_path` i wylicza score 0-100 per moduł. Sortowane rosnąco po liczbie findings (najgorsze pierwsze).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/modules' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/modules",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/modules', {
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

### `POST /api/v1/projects/{project_id}/compliance/snapshot`

Create Compliance Snapshot.

**Utwórz snapshot compliance (Story 5.7).**

Przechwytuje aktualny stan compliance (score + breakdown + counts) jako punkt w czasie. Snapshots pozwalają na porównanie wersji i trend.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `SnapshotCreateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `201` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/snapshot' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"label": "przykladowa-wartosc", "notes": "przykladowa-wartosc"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/snapshot",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "label": "przykladowa-wartosc",
      "notes": "przykladowa-wartosc"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/snapshot', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "label": "przykladowa-wartosc",
    "notes": "przykladowa-wartosc"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/compliance/snapshots`

List Compliance Snapshots.

List all compliance snapshots for the project, newest first.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/snapshots' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/snapshots",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/snapshots', {
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

### `GET /api/v1/projects/{project_id}/compliance/trend`

Get Compliance Trend.

Get compliance trend data across snapshots (oldest to newest).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `limit` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/trend' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/trend",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/compliance/trend', {
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

### `POST /api/v1/projects/{project_id}/gap-analysis`

Start Gap Analysis.

**Uruchom analizę luk funkcjonalnych (Epic 5, FR38).**

Asynchronicznie porównuje wymagania z dokumentacji z bytami kodu przy użyciu 3 algorytmów fuzzy matching (Levenshtein, Jaro-Winkler, TF-IDF cosine). Klasyfikuje wynik w 4 typy luk (missing/different/extra/inconsistent).

Tryb `engine_mode`:
- `native` (domyślnie) — deterministyczny, offline
- `llm` — semantyczna analiza przez LLMGateway
- `hybrid` — łączy native + LLM, najwyższy recall

Wymaga uprzedniego uruchomienia analizy dokumentu (requirements) i skanowania kodu (logic_structures). Zwraca `task_id` do śledzenia w `/tasks/{task_id}`.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `GapAnalysisRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Analiza zaplanowana — zwraca task_id do śledzenia. |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Brak kontekstu tenant. |
| `404` | Projekt nie znaleziony lub brak dostępu w tenant. |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-analysis' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"document_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"], "engine_mode": "native"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-analysis",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "document_ids": [
        "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      ],
      "engine_mode": "native"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-analysis', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "document_ids": [
      "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    ],
    "engine_mode": "native"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/gap-analysis/summary`

Get Gap Analysis Summary.

**Podsumowanie analizy luk.**

Zwraca łączną liczbę wymagań, bytów kodu, liczebności per typ luki, średni score dopasowania i procent pokrycia (coverage %).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-analysis/summary' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-analysis/summary",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-analysis/summary', {
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

### `GET /api/v1/projects/{project_id}/gap-findings`

List Gap Findings.

**Lista znalezisk luk (Epic 5, FR39).**

Paginowana lista z filtrami:
- `gap_type` — missing | different | extra | inconsistent
- `severity` — info | warning | critical
- `min_score` — 0.0-100.0
- `match_method` — lev | jw | sem | combined | hybrid | llm

Wynik zawiera podsumowanie (`summary`) wyliczone dla całego projektu, nie tylko bieżącej strony.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `gap_type` | query | nie |  |
| `min_score` | query | nie |  |
| `severity` | query | nie |  |
| `match_method` | query | nie |  |
| `page` | query | nie |  |
| `size` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings', {
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

### `GET /api/v1/projects/{project_id}/gap-findings/by-type`

List Gap Findings Grouped.

List gap findings grouped by gap_type with counts and percentages.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/by-type' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/by-type",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/by-type', {
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

### `GET /api/v1/projects/{project_id}/gap-findings/{finding_id}/skeleton`

Get Skeleton.

Retrieve previously generated skeleton code for a gap finding.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `finding_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/skeleton' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/skeleton",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/skeleton', {
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

### `POST /api/v1/projects/{project_id}/gap-findings/{finding_id}/skeleton`

Generate Skeleton.

**Generuj skeleton kodu (Story 5.6).**

Dostępne tylko dla findings typu `missing`. Produkuje plik źródłowy ze stub implementacji (`NotImplementedError` / `UnsupportedOperationException`).

Obsługiwane języki: `python`, `typescript`, `java`, `csharp`.

Skeleton jest walidowany tree-sitter — gwarancja poprawnej składni. Wynik jest persystowany na `finding.skeleton_code` + `skeleton_language`.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `finding_id` | path | tak |  |

**Ciało żądania:** `SkeletonGenerateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Skeleton wygenerowany |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `404` | Finding nie znaleziony. |
| `422` | Finding nie jest typu missing, lub błąd składni. |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/skeleton' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"language": "python"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/skeleton",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "language": "python"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gap-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/skeleton', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "language": "python"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/recommendations`

List Recommendations.

**Lista rekomendacji.**

Paginowana lista z filtrami:
- `priority` — P1 | P2 | P3 | P4
- `source_type` — native | llm | hybrid
- `min_confidence` — 0.0-1.0

Każda rekomendacja ma `suggested_action`, `effort_estimate` (S/M/L) i powiązanie do `gap_finding_id`.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `priority` | query | nie |  |
| `source_type` | query | nie |  |
| `min_confidence` | query | nie |  |
| `page` | query | nie |  |
| `size` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations', {
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

### `POST /api/v1/projects/{project_id}/recommendations/generate`

Generate Recommendations.

**Generuj rekomendacje naprawcze (Epic 5, FR42).**

Uruchamia asynchroniczny task, który dla każdej luki w `gap_findings` produces actionable rekomendację z:
- `priority` (P1 natychmiat → P4 niski)
- `confidence` (0.0-1.0)
- `effort_estimate` (S/M/L)
- `suggested_action` (tekst)

Źródła:
- `native` — template-based, deterministyczne (confidence 0.7)
- `llm` — semantyczne przez LLMGateway
- `hybrid` — oba źródła połączone

Mapowanie priorytetów: missing+critical=P1, different+critical=P1, inconsistent zawsze P1, missing+warning=P2, extra+info=P4.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `RecommendationGenerateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations/generate' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"sources": ["gap_finding"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations/generate",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "sources": [
        "gap_finding"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations/generate', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "sources": [
      "gap_finding"
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

### `GET /api/v1/projects/{project_id}/recommendations/summary`

Get Recommendation Summary.

Get summary of recommendations for the project.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations/summary' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations/summary",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendations/summary', {
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

### `GET /api/v1/projects/{project_id}/traceability`

Get Traceability Matrix.

Paginated, filterable traceability matrix plus a coverage summary (AC-1, AC-3).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `source_type` | query | nie |  |
| `coverage_status` | query | nie |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability', {
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

### `POST /api/v1/projects/{project_id}/traceability/build`

Build Traceability Matrix Route.

Trigger an asynchronous (re)build of the traceability matrix (AC-5).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability/build' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability/build",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability/build', {
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

### `GET /api/v1/projects/{project_id}/traceability/export`

Export Traceability Matrix.

Export the full traceability matrix in the requested format (AC-6).

CSV/JSON are native; XLSX/PDF require optional libs and return 501 if absent.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability/export' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability/export",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/traceability/export', {
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
