# Raporty i eksport

> Plik generowany ze schemy OpenAPI przez `python -m scripts.generate_api_docs`.
> Nie edytuj ręcznie — zmiany nadpisze kolejne uruchomienie.

Generowanie i pobieranie raportów w formatach PDF, HTML, CSV, Excel, JSON i YAML. Eksport przypadków do systemów TMS opisuje [Integracja z TMS](../tms-integration.md).

Liczba endpointów: **3**.

[↩ Powrót do spisu treści](../index.md)

---

### `GET /api/v1/exports/{export_id}/download`

Download Export.

Pobranie gotowego pliku z Content-Disposition (AC8).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `export_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/exports/3fa85f64-5717-4562-b3fc-2c963f66afa6/download' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/exports/3fa85f64-5717-4562-b3fc-2c963f66afa6/download",
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

const response = await fetch('http://localhost:8000/api/v1/exports/3fa85f64-5717-4562-b3fc-2c963f66afa6/download', {
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

### `GET /api/v1/exports/{export_id}/status`

Get Export Status.

Status generowania eksportu — polling z FE (AC1/AC7).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `export_id` | path | tak |  |

| Kod | Znaczenie |
| :-: | --- |
| `200` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X GET 'http://localhost:8000/api/v1/exports/3fa85f64-5717-4562-b3fc-2c963f66afa6/status' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.get(
    "http://localhost:8000/api/v1/exports/3fa85f64-5717-4562-b3fc-2c963f66afa6/status",
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

const response = await fetch('http://localhost:8000/api/v1/exports/3fa85f64-5717-4562-b3fc-2c963f66afa6/status', {
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

### `POST /api/v1/projects/{project_id}/reports/export`

Request Report Export.

Rozpoczyna asynchroniczne generowanie pliku eksportu (AC1-AC7).

**Uwierzytelnianie:** wymagane

| Parametr | W | Wymagany | Opis |
| --- | --- | :-: | --- |
| `project_id` | path | tak |  |

**Ciało żądania:** `ReportExportRequest`

| Kod | Znaczenie |
| :-: | --- |
| `202` | Successful Response |
| `401` | Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API) |
| `403` | Poświadczenia poprawne, ale bez uprawnień do tej operacji |
| `422` | Validation Error |
| `429` | Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić. |

<details><summary>Przykład — curl</summary>

```bash
curl -X POST 'http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/reports/export' \
  -H 'Authorization: Bearer tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
  -H 'Content-Type: application/json' \
  -d '{"format": "pdf", "report": {"conclusions": ["przykladowa-wartosc"], "findings": [{"code_snippet": null, "cvss_score": null, "cwe_id": null, "description": null, "file_path": null, "id": null, "language": null, "line_start": null}], "generated_at": "", "kpis": {"compliance_score": 1.0, "coverage_percentage": 1.0, "critical_count": 0, "high_count": 0, "low_count": 0, "medium_count": 0, "test_cases_passed": 0, "test_cases_ready": 0}, "module_scores": [{"file_path": null, "score": null, "total_findings": null}], "project_id": "", "severity_counts": {}, "trend_points": [{"label": null, "score": null, "timestamp": null}]}, "report_type": "both"}'
```

</details>

<details><summary>Przykład — Python (requests)</summary>

```python
import requests

API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # Ustawienia → Klucze API

response = requests.post(
    "http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/reports/export",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
      "format": "pdf",
      "report": {
        "conclusions": [
          "przykladowa-wartosc"
        ],
        "findings": [
          {
            "code_snippet": null,
            "cvss_score": null,
            "cwe_id": null,
            "description": null,
            "file_path": null,
            "id": null,
            "language": null,
            "line_start": null
          }
        ],
        "generated_at": "",
        "kpis": {
          "compliance_score": 1.0,
          "coverage_percentage": 1.0,
          "critical_count": 0,
          "high_count": 0,
          "low_count": 0,
          "medium_count": 0,
          "test_cases_passed": 0,
          "test_cases_ready": 0
        },
        "module_scores": [
          {
            "file_path": null,
            "score": null,
            "total_findings": null
          }
        ],
        "project_id": "",
        "severity_counts": {},
        "trend_points": [
          {
            "label": null,
            "score": null,
            "timestamp": null
          }
        ]
      },
      "report_type": "both"
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

const response = await fetch('http://localhost:8000/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6/reports/export', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    "format": "pdf",
    "report": {
      "conclusions": [
        "przykladowa-wartosc"
      ],
      "findings": [
        {
          "code_snippet": null,
          "cvss_score": null,
          "cwe_id": null,
          "description": null,
          "file_path": null,
          "id": null,
          "language": null,
          "line_start": null
        }
      ],
      "generated_at": "",
      "kpis": {
        "compliance_score": 1.0,
        "coverage_percentage": 1.0,
        "critical_count": 0,
        "high_count": 0,
        "low_count": 0,
        "medium_count": 0,
        "test_cases_passed": 0,
        "test_cases_ready": 0
      },
      "module_scores": [
        {
          "file_path": null,
          "score": null,
          "total_findings": null
        }
      ],
      "project_id": "",
      "severity_counts": {},
      "trend_points": [
        {
          "label": null,
          "score": null,
          "timestamp": null
        }
      ]
    },
    "report_type": "both"
  }),
});

if (!response.ok) {
  throw new Error(`TestGEN API: ${response.status}`);
}
console.log(await response.json());
```

</details>

---
