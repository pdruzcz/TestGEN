# Analiza

> Plik generowany ze schemy OpenAPI przez `python -m scripts.generate_api_docs`.
> Nie edytuj ręcznie — zmiany nadpisze kolejne uruchomienie.

Uruchamianie analiz, śledzenie zadań w tle oraz odczyt wyników analizy dokumentacji, diagramów UML i zrzutów GUI.

Liczba endpointów: **42**.

[↩ Powrót do spisu treści](../index.md)

---

### `GET /api/v1/dashboard/audit-logs`

Get Dashboard Audit Logs.

**Activity feed — ostatnie logi audytu (Story 6.1).**

Zwraca listę wpisów z `audit_logs` dla bieżącego tenanta. Używane przez frontend z pollingiem co 30s (rxjs `interval(30000)`).

Limit domyślnie 20, max 50.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
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
curl -X GET 'http://localhost:8000/api/v1/dashboard/audit-logs' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/dashboard/audit-logs",
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

const response = await fetch('http://localhost:8000/api/v1/dashboard/audit-logs', {
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

### `GET /api/v1/dashboard/summary`

Get Dashboard Summary.

**Dashboard główny — zagregowane podsumowanie (Story 6.1).**

Zwraca w jednej odpowiedzi:
- listę projektów z compliance % (najnowszy snapshot), liczbą testów, ostatnią analizą
- 4 karty statystyk: liczba projektów, analiz w tym miesiącu, avg compliance, aktywni użytkownicy
- widget użycia planu (tylko dla Owner/Admin; `null` dla Member)

Aktywność (activity feed) pobierana osobnym endpointem `/dashboard/audit-logs` z pollingiem co 30s.

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
curl -X GET 'http://localhost:8000/api/v1/dashboard/summary' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/dashboard/summary",
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

const response = await fetch('http://localhost:8000/api/v1/dashboard/summary', {
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

### `GET /api/v1/documents/{document_id}/analysis`

Get Document Analysis.

Get complete analysis results for a document.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/analysis' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/analysis",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/analysis', {
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

### `GET /api/v1/documents/{document_id}/classification`

Get Document Classification.

Get the persisted document classification (AC1).

404 when the document is missing, 202 when preprocessing or classification
is not yet available, 200 with the classification otherwise.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/classification' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/classification",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/classification', {
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

### `POST /api/v1/documents/{document_id}/classify`

Classify Document.

Classify a document by the global ``engine_mode`` (AC1).

No request body — the engine mode comes from ``Settings`` only. The result
is upserted into ``AnalysisResult(module="classification")``.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/classify' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/classify",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/classify', {
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

### `POST /api/v1/documents/{document_id}/compare`

Compare Analysis Modes.

Compare native vs LLM analysis results.

The comparison is an analytical feature (native-vs-LLM coverage delta),
independent of the configured ``engine_mode``. Requirement extraction is
native-only today (LLM extraction is unimplemented), so both sides return
identical results until LLM extraction lands.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/compare' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/compare",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/compare', {
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

### `GET /api/v1/documents/{document_id}/glossary`

Get Glossary.

Get persisted glossary terms for a document (AC4).

Reads ``AnalysisResult.result_data["terms"]``. 404 when the document is
missing, 202 when glossary is not yet available, 200 with the list otherwise.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary', {
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

### `POST /api/v1/documents/{document_id}/glossary/map-to-code`

Map Glossary To Code.

Rebuild code mappings for every term against the project's code analysis
(AC4, AC2). Sync in v1 (small term sets); persists ``code_mappings`` into
result_data and returns the updated list.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary/map-to-code' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary/map-to-code",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary/map-to-code', {
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

### `PUT /api/v1/documents/{document_id}/glossary/{term}`

Update Glossary Term.

Edit a glossary term — mutates definition/term_type/is_verified and
confirms code mappings (AC4). Term match is case-insensitive.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |
| `term` | path | tak |  |

**Ciało żądania:** `GlossaryTermUpdateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X PUT 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary/przykladowa-wartosc' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"confirmed_mapping_ids": ["przykladowa-wartosc"], "definition": "przykladowa-wartosc", "is_verified": true, "term_type": "przykladowa-wartosc"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.put(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary/przykladowa-wartosc",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "confirmed_mapping_ids": [
        "przykladowa-wartosc"
      ],
      "definition": "przykladowa-wartosc",
      "is_verified": true,
      "term_type": "przykladowa-wartosc"
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/glossary/przykladowa-wartosc', {
  method: 'PUT',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "confirmed_mapping_ids": [
      "przykladowa-wartosc"
    ],
    "definition": "przykladowa-wartosc",
    "is_verified": true,
    "term_type": "przykladowa-wartosc"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/documents/{document_id}/inconsistencies`

Get Inconsistencies.

Get persisted inconsistencies for a document (AC3).

Reads ``AnalysisResult.result_data["items"]``. 404 when the document is
missing, 202 when inconsistencies are not yet available, 200 with the list
and workflow statuses otherwise.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/inconsistencies' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/inconsistencies",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/inconsistencies', {
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

### `PUT /api/v1/documents/{document_id}/inconsistencies/{inconsistency_id}`

Update Inconsistency Status.

Update an inconsistency's workflow status (AC4) — mutates ``status``
(open/accepted/false_positive/fixed) in ``result_data`` and persists it.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |
| `inconsistency_id` | path | tak |  |

**Ciało żądania:** `InconsistencyStatusUpdateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X PUT 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/inconsistencies/przykladowa-wartosc' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"status": "open"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.put(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/inconsistencies/przykladowa-wartosc",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/inconsistencies/przykladowa-wartosc', {
  method: 'PUT',
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

### `POST /api/v1/documents/{document_id}/reparse`

Reparse Document.

Re-run document parsing (sections / requirements / glossary) on demand.

Resets the file to ``PROCESSING``, clears any prior error and dispatches
the existing ``parse_document_task``. No quota is consumed — document
parsing is free, unlike ``POST /projects/{id}/analyze`` which analyses
source code and is quota-gated. Returns 202 + ``task_id`` so the client
can poll status exactly like after upload.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/reparse' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/reparse",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/reparse', {
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

### `GET /api/v1/documents/{document_id}/requirements`

Get Requirements.

Get persisted requirements for a document (AC2).

Reads the requirements persisted by the parsing task from
``AnalysisResult.result_data["requirements"]``. 404 when the document is
missing, 202 when requirements are not yet available, 200 with the list and
workflow statuses otherwise.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements', {
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

### `PUT /api/v1/documents/{document_id}/requirements/{req_id}`

Update Requirement.

Edit a requirement — mutates text/priority and sets status (AC3).

An explicit ``status`` (``accepted``/``rejected``/``extracted``/``edited``)
wins; otherwise any text/priority change marks the element ``edited``.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |
| `req_id` | path | tak |  |

**Ciało żądania:** `RequirementUpdateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X PUT 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"priority": "przykladowa-wartosc", "status": "przykladowa-wartosc", "text": "przykladowa-wartosc"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.put(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "priority": "przykladowa-wartosc",
      "status": "przykladowa-wartosc",
      "text": "przykladowa-wartosc"
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc', {
  method: 'PUT',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "priority": "przykladowa-wartosc",
    "status": "przykladowa-wartosc",
    "text": "przykladowa-wartosc"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/documents/{document_id}/requirements/{req_id}/accept`

Accept Requirement.

Accept a requirement — sets its workflow status to ``accepted`` (AC3).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |
| `req_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc/accept' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc/accept",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc/accept', {
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

### `POST /api/v1/documents/{document_id}/requirements/{req_id}/reject`

Reject Requirement.

Reject a requirement — sets its workflow status to ``rejected`` (AC3).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |
| `req_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc/reject' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc/reject",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/requirements/przykladowa-wartosc/reject', {
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

### `GET /api/v1/documents/{document_id}/sections`

Get Document Sections.

Get document sections reconstructed as a tree (AC1).

Reads the sections persisted by the preprocessing task in
``AnalysisResult.result_data["sections"]`` and rebuilds the parent-child
hierarchy from ``parent_section_id``.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/sections' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/sections",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/sections', {
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

### `GET /api/v1/documents/{document_id}/sections/{section_id}`

Get Document Section.

Get a single section by ID with its content (AC2). 404 if not found.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |
| `section_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/sections/przykladowa-wartosc' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/sections/przykladowa-wartosc",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/sections/przykladowa-wartosc', {
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

### `GET /api/v1/documents/{document_id}/status`

Get Analysis Status.

Get the current status of document analysis.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `document_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/status' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/status",
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

const response = await fetch('http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/status', {
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

### `POST /api/v1/projects/{project_id}/analyze`

Start Analysis.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `AnalysisRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/analyze' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"engine_mode": "native", "modules": ["code_analysis", "security_scan"], "test_framework": "pytest"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/analyze",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "engine_mode": "native",
      "modules": [
        "code_analysis",
        "security_scan"
      ],
      "test_framework": "pytest"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/analyze', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "engine_mode": "native",
    "modules": [
      "code_analysis",
      "security_scan"
    ],
    "test_framework": "pytest"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/files/{file_id}/analyze`

Analyze File.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `file_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/files/3fa85f64-5717-4562-b3fc-2c963f66afa6/analyze' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/files/3fa85f64-5717-4562-b3fc-2c963f66afa6/analyze",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/files/3fa85f64-5717-4562-b3fc-2c963f66afa6/analyze', {
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

### `GET /api/v1/projects/{project_id}/gui`

List Gui Route.

Paginated list of a project's GUI screenshots.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui', {
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

### `GET /api/v1/projects/{project_id}/gui/analyses`

List Gui Analyses Route.

Paginated GUI analysis history (screenshot + DOM) — Story 1.51-zakańczenie B1.

Powers the healing launcher's before/after version selectors (Part B2).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/analyses' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/analyses",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/analyses', {
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

### `POST /api/v1/projects/{project_id}/gui/analyze`

Analyze Gui Route.

Force (re)analysis of a specific screenshot. Dispatches the Celery task.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `GUIAnalyzeRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/analyze' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/analyze",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/analyze', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/gui/compare`

Compare Gui Route.

Compare two GUI screenshots synchronously and persist the result (Story 3.10).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `VisualRegressionRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/compare' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"baseline_screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "comparison_screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "generate_test_code": false, "pixel_threshold": 0.02, "test_framework": "playwright"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/compare",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "baseline_screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "comparison_screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "generate_test_code": false,
      "pixel_threshold": 0.02,
      "test_framework": "playwright"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/compare', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "baseline_screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "comparison_screenshot_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "generate_test_code": false,
    "pixel_threshold": 0.02,
    "test_framework": "playwright"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/gui/comparisons`

List Gui Comparisons Route.

Paginated list of stored visual-regression comparisons for a project (Story 3.10).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/comparisons' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/comparisons",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/comparisons', {
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

### `GET /api/v1/projects/{project_id}/gui/comparisons/{comparison_id}/diff`

Get Comparison Diff Route.

Stream the stored annotated diff-image of a comparison (Story 3.10).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `comparison_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/comparisons/3fa85f64-5717-4562-b3fc-2c963f66afa6/diff' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/comparisons/3fa85f64-5717-4562-b3fc-2c963f66afa6/diff",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/comparisons/3fa85f64-5717-4562-b3fc-2c963f66afa6/diff', {
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

### `POST /api/v1/projects/{project_id}/gui/dom/upload`

Upload Gui Dom Route.

Upload HTML/DOM as a GUI source (sibling of screenshots) — Story 1.51-zakańczenie A2.

Origin-based routing: HTML entering here is analysed as GUI structure and
feeds self-healing with real locator attributes. HTML routed as documentation
still goes to the E2 ``HTMLParser``; HTML in a code bundle stays code.

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
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/dom/upload' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/dom/upload",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/dom/upload', {
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

### `GET /api/v1/projects/{project_id}/gui/flows`

List Gui Flows Route.

Paginated list of GUI-reconstructed user flows for a project (Story 3.9).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/flows' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/flows",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/flows', {
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

### `POST /api/v1/projects/{project_id}/gui/flows`

Reconstruct Gui Flows Route.

Dispatch reconstruction of a GUI user flow from a screenshot sequence (Story 3.9).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `GUIFlowReconstructionRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/flows' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"name": "przykladowa-wartosc", "screenshot_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/flows",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "name": "przykladowa-wartosc",
      "screenshot_ids": [
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/flows', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "name": "przykladowa-wartosc",
    "screenshot_ids": [
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

### `POST /api/v1/projects/{project_id}/gui/upload`

Upload Gui Route.

Upload GUI screenshots. Analysis is dispatched asynchronously per file.

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
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/upload' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/upload",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/upload', {
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

### `GET /api/v1/projects/{project_id}/gui/{screenshot_id}/result`

Get Gui Result Route.

Screenshot analysis result: OCR text blocks, components and layout tree.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `screenshot_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/3fa85f64-5717-4562-b3fc-2c963f66afa6/result' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/3fa85f64-5717-4562-b3fc-2c963f66afa6/result",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/gui/3fa85f64-5717-4562-b3fc-2c963f66afa6/result', {
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

### `GET /api/v1/projects/{project_id}/uml`

List Uml Route.

Paginated list of the project's UML diagrams.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml', {
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

### `POST /api/v1/projects/{project_id}/uml/analyze`

Analyze Cross Diagrams Route.

Launch asynchronous cross-diagram analysis (Story 3.7). Returns a task id.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `CrossAnalysisRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/analyze' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"diagram_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/analyze",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "diagram_ids": [
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/analyze', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "diagram_ids": [
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

### `GET /api/v1/projects/{project_id}/uml/flows`

List Flows Route.

Paginated list of user flows reconstructed for the project (Story 3.7).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/flows' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/flows",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/flows', {
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

### `GET /api/v1/projects/{project_id}/uml/flows/{flow_id}`

Get Flow Route.

User flow details with its ordered steps (Story 3.7).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `flow_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/flows/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/flows/3fa85f64-5717-4562-b3fc-2c963f66afa6",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/flows/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
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

### `POST /api/v1/projects/{project_id}/uml/parse`

Parse Uml Route.

Force (re)parsing of a specific diagram. Dispatches the Celery task.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `UMLParseRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/parse' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"diagram_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/parse",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "diagram_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/parse', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "diagram_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/uml/upload`

Upload Uml Route.

Upload UML diagrams (XMI / PlantUML). Async parsing is dispatched per file.

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
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/upload' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/upload",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/upload', {
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

### `GET /api/v1/projects/{project_id}/uml/{diagram_id}`

Get Uml Route.

Diagram details plus the parsed structural model (if available).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `diagram_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/3fa85f64-5717-4562-b3fc-2c963f66afa6",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
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

### `POST /api/v1/projects/{project_id}/uml/{diagram_id}/compare-code`

Compare Code Route.

Compare a parsed class diagram with the project's source code (Story 3.4).

Code structure comes from the project's ``logic_structures`` (Epic 1 AST
analysis) via ``LogicStructuresCodeProvider``. When the project has no code
analysis yet, the provider yields an empty structure and every diagram class
is reported as ``diagram_only``.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `diagram_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/3fa85f64-5717-4562-b3fc-2c963f66afa6/compare-code' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/3fa85f64-5717-4562-b3fc-2c963f66afa6/compare-code",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/uml/3fa85f64-5717-4562-b3fc-2c963f66afa6/compare-code', {
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

### `GET /api/v1/tasks/{task_id}`

Get Task Status.

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `task_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/tasks/przykladowa-wartosc' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/tasks/przykladowa-wartosc",
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

const response = await fetch('http://localhost:8000/api/v1/tasks/przykladowa-wartosc', {
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

### `POST /api/v1/tasks/{task_id}/cancel`

Cancel Task.

Anuluj uruchomione zadanie analizy (Story 6.3, AC5).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `task_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/tasks/przykladowa-wartosc/cancel' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/tasks/przykladowa-wartosc/cancel",
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

const response = await fetch('http://localhost:8000/api/v1/tasks/przykladowa-wartosc/cancel', {
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
