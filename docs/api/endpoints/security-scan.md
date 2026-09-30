# Bezpieczeństwo

> Plik generowany ze schemy OpenAPI przez `python -m scripts.generate_api_docs`.
> Nie edytuj ręcznie — zmiany nadpisze kolejne uruchomienie.

Skany bezpieczeństwa (SAST, taint analysis, zależności, konfiguracja, DAST), znaleziska i rekomendacje naprawcze.

Liczba endpointów: **20**.

[↩ Powrót do spisu treści](../index.md)

---

### `GET /api/v1/admin/cve-pipeline/logs`

List Pipeline Logs.

Return the CVE update run history (most recent first).

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
curl -X GET 'http://localhost:8000/api/v1/admin/cve-pipeline/logs' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/admin/cve-pipeline/logs",
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

const response = await fetch('http://localhost:8000/api/v1/admin/cve-pipeline/logs', {
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

### `GET /api/v1/admin/cve-pipeline/status`

Get Pipeline Status.

Return the latest pipeline run summary for the admin dashboard.

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
curl -X GET 'http://localhost:8000/api/v1/admin/cve-pipeline/status' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/admin/cve-pipeline/status",
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

const response = await fetch('http://localhost:8000/api/v1/admin/cve-pipeline/status', {
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

### `POST /api/v1/admin/cve-pipeline/trigger`

Trigger Pipeline.

Manually enqueue a CVE database update (admin only).

**Uwierzytelnianie:** wymagane

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/admin/cve-pipeline/trigger' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/admin/cve-pipeline/trigger",
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

const response = await fetch('http://localhost:8000/api/v1/admin/cve-pipeline/trigger', {
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

### `GET /api/v1/projects/{project_id}/security-dashboard`

Get Security Dashboard.

Return the risk dashboard: CVSS distribution, top 10 and repair sequence (AC3).

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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-dashboard' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-dashboard",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-dashboard', {
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

### `GET /api/v1/projects/{project_id}/security-findings`

List Security Findings.

List findings for a project with optional filters (AC3).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `scan_id` | query | nie |  |
| `severity` | query | nie |  |
| `scan_type` | query | nie |  |
| `status` | query | nie |  |
| `vulnerability_type` | query | nie |  |
| `file_path` | query | nie |  |
| `cwe_id` | query | nie |  |
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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings', {
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

### `POST /api/v1/projects/{project_id}/security-findings/{finding_id}/generate-patch`

Generate Finding Patch.

Generate a git-apply-ready unified-diff patch for a finding (AC1, AC2).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `finding_id` | path | tak |  |

**Ciało żądania:** `PatchRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/generate-patch' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/generate-patch",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={},
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/generate-patch', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({}),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `POST /api/v1/projects/{project_id}/security-findings/{finding_id}/generate-poc`

Generate Finding Poc.

Generate a safe, non-destructive PoC for an injection finding (AC1-AC4).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `finding_id` | path | tak |  |

**Ciało żądania:** `PoCRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/generate-poc' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/generate-poc",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={},
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/generate-poc', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({}),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/security-findings/{finding_id}/patch`

Get Finding Patch.

Return a previously generated patch for a finding (AC2).

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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch', {
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

### `GET /api/v1/projects/{project_id}/security-findings/{finding_id}/patch/download`

Download Finding Patch.

Download the stored patch as a ``.patch`` file applicable via ``git apply`` (AC2).

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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch/download' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch/download",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch/download', {
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

### `GET /api/v1/projects/{project_id}/security-findings/{finding_id}/patch/preview`

Preview Finding Patch.

Preview before/after code and the diff without persisting (AC2).

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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch/preview' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch/preview",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/patch/preview', {
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

### `GET /api/v1/projects/{project_id}/security-findings/{finding_id}/poc`

Get Finding Poc.

Return a previously generated PoC for a finding (AC1, AC4).

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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/poc' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/poc",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/poc', {
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

### `POST /api/v1/projects/{project_id}/security-findings/{finding_id}/recommendation`

Generate Finding Recommendation.

Generate a remediation recommendation (problem/risk/fix/diff) for a finding (AC1-AC4).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `finding_id` | path | tak |  |

**Ciało żądania:** `RecommendationRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendation' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendation",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={},
    timeout=30,
)
response.raise_for_status()
print(response.json() if response.content else response.status_code)
```

</details>

<details><summary>Przykład — JavaScript (fetch)</summary>

```javascript
const apiKey = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'; // Ustawienia → Klucze API

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/recommendation', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({}),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `PATCH /api/v1/projects/{project_id}/security-findings/{finding_id}/status`

Update Finding Status.

Change a finding's triage status (acknowledge / false_positive / fixed).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `finding_id` | path | tak |  |

**Ciało żądania:** `FindingStatusUpdateRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X PATCH 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/status' \
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
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/status",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-findings/3fa85f64-5717-4562-b3fc-2c963f66afa6/status', {
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

### `POST /api/v1/projects/{project_id}/security-patches/batch`

Generate Batch Patches.

Generate one patch per finding and report same-file conflicts (AC3).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `BatchPatchRequest`

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-patches/batch' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"finding_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-patches/batch",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "finding_ids": [
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-patches/batch', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "finding_ids": [
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

### `GET /api/v1/projects/{project_id}/security-patches/conflicts`

List Patch Conflicts.

List potential merge conflicts between findings in the same file (AC3).

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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-patches/conflicts' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-patches/conflicts",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-patches/conflicts', {
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

### `GET /api/v1/projects/{project_id}/security-report`

Get Security Report.

Return the aggregated, deduplicated, correlated security report (AC2).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `scan_id` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-report' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-report",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-report', {
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

### `POST /api/v1/projects/{project_id}/security-scan`

Start Security Scan.

Create a scan record and dispatch the async scan task (AC1).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `SecurityScanRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scan' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"auth_config": {"auth_type": "form", "login_url": "przykladowa-wartosc", "password": "przykladowa-wartosc", "password_field": "przykladowa-wartosc", "token": "przykladowa-wartosc", "username": "przykladowa-wartosc", "username_field": "przykladowa-wartosc"}, "scan_type": "sast", "target_url": "przykladowa-wartosc"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scan",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "auth_config": {
        "auth_type": "form",
        "login_url": "przykladowa-wartosc",
        "password": "przykladowa-wartosc",
        "password_field": "przykladowa-wartosc",
        "token": "przykladowa-wartosc",
        "username": "przykladowa-wartosc",
        "username_field": "przykladowa-wartosc"
      },
      "scan_type": "sast",
      "target_url": "przykladowa-wartosc"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scan', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "auth_config": {
      "auth_type": "form",
      "login_url": "przykladowa-wartosc",
      "password": "przykladowa-wartosc",
      "password_field": "przykladowa-wartosc",
      "token": "przykladowa-wartosc",
      "username": "przykladowa-wartosc",
      "username_field": "przykladowa-wartosc"
    },
    "scan_type": "sast",
    "target_url": "przykladowa-wartosc"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---

### `GET /api/v1/projects/{project_id}/security-scans`

List Security Scans.

List the project's scans, most recent first (AC1).

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
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans', {
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

### `GET /api/v1/projects/{project_id}/security-scans/{scan_id}`

Get Security Scan.

Return a scan's status plus a per-severity findings breakdown (AC1, AC3).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `scan_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans/3fa85f64-5717-4562-b3fc-2c963f66afa6",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans/3fa85f64-5717-4562-b3fc-2c963f66afa6', {
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

### `GET /api/v1/projects/{project_id}/security-scans/{scan_id}/sbom`

Get Scan Sbom.

Return the generated SBOM for a dependency scan (Story 4.4).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |
| `scan_id` | path | tak |  |
| `sbom_format` | query | nie |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans/3fa85f64-5717-4562-b3fc-2c963f66afa6/sbom' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans/3fa85f64-5717-4562-b3fc-2c963f66afa6/sbom",
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/security-scans/3fa85f64-5717-4562-b3fc-2c963f66afa6/sbom', {
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
