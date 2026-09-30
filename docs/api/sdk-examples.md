# Przykłady i szybki start

Ta strona pokazuje pełny przepływ — od wysłania kodu po odczyt werdyktu —
w trzech językach. Każdy przykład da się wkleić i uruchomić po podmienieniu
adresu, klucza i identyfikatora projektu.

TestGEN nie dostarcza dedykowanego SDK: API jest zwykłym REST‑em nad JSON‑em,
więc wystarczy biblioteka HTTP, którą i tak masz w projekcie.

## Zanim zaczniesz

| Co | Skąd |
| --- | --- |
| Klucz API | *Ustawienia → Klucze API*, zakres **pełny dostęp** |
| Identyfikator projektu | adres strony projektu |
| Adres API | np. `https://api.testgen.io` |

Klucze w przykładach poniżej są fikcyjne — mają poprawny format, ale nie działają.

## Pełny przepływ: analiza projektu

### curl

```bash
#!/usr/bin/env bash
set -euo pipefail

API_URL="https://api.testgen.io"
API_KEY="tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
PROJECT_ID="3fa85f64-5717-4562-b3fc-2c963f66afa6"

# 1. Spakuj kod — upload przyjmuje archiwa i rozpakuje je po stronie serwera.
zip -qr zrodla.zip . -x ".git/*" -x "node_modules/*" -x "*.zip"

# 2. Wyślij kod.
curl --fail-with-body --silent --show-error \
  -X POST "$API_URL/api/v1/projects/$PROJECT_ID/upload" \
  -H "Authorization: Bearer $API_KEY" \
  -F "files=@zrodla.zip"

# 3. Uruchom analizę.
TASK_ID=$(curl --fail-with-body --silent --show-error \
  -X POST "$API_URL/api/v1/projects/$PROJECT_ID/analyze" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"engine_mode": "native", "modules": ["code_analysis", "security_scan"]}' \
  | jq -r '.task_id')

# 4. Czekaj na wynik — odstęp 10 s wystarcza i nie zjada limitu żądań.
for _ in $(seq 1 180); do
  STATUS=$(curl --fail-with-body --silent --show-error \
    "$API_URL/api/v1/tasks/$TASK_ID" \
    -H "Authorization: Bearer $API_KEY" | jq -r '.status')
  case "$STATUS" in
    completed|success) break ;;
    failed|error) echo "Analiza zakończona błędem"; exit 1 ;;
  esac
  sleep 10
done

# 5. Sprawdź werdykt — próg liczy serwer, nie ten skrypt.
curl --fail-with-body --silent --show-error \
  "$API_URL/api/v1/projects/$PROJECT_ID/ci-cd/summary?threshold=critical" \
  -H "Authorization: Bearer $API_KEY" | jq '.'
```

### Python

```python
"""Analiza projektu w TestGEN — od wysłania kodu po werdykt."""

import shutil
import time
from pathlib import Path

import requests

API_URL = "https://api.testgen.io"
API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
PROJECT_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

session = requests.Session()
session.headers["Authorization"] = f"Bearer {API_KEY}"


def upload_sources(directory: Path) -> None:
    """Wysyła katalog jako archiwum — jedno żądanie zamiast setek."""
    archive = Path(shutil.make_archive("zrodla", "zip", directory))
    try:
        with archive.open("rb") as handle:
            response = session.post(
                f"{API_URL}/api/v1/projects/{PROJECT_ID}/upload",
                files={"files": (archive.name, handle, "application/zip")},
                timeout=300,
            )
        response.raise_for_status()
    finally:
        archive.unlink(missing_ok=True)


def start_analysis() -> str:
    response = session.post(
        f"{API_URL}/api/v1/projects/{PROJECT_ID}/analyze",
        json={"engine_mode": "native", "modules": ["code_analysis", "security_scan"]},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["task_id"]


def wait_for(task_id: str, *, timeout_minutes: int = 30) -> None:
    """Odpytuje co 10 s — częściej nie ma sensu i zjada limit żądań."""
    deadline = time.monotonic() + timeout_minutes * 60
    while time.monotonic() < deadline:
        response = session.get(f"{API_URL}/api/v1/tasks/{task_id}", timeout=30)
        response.raise_for_status()
        status = response.json()["status"]
        if status in ("completed", "success"):
            return
        if status in ("failed", "error"):
            raise RuntimeError(f"Analiza zakończona błędem: {response.json().get('error')}")
        time.sleep(10)
    raise TimeoutError(f"Analiza nie zakończyła się w ciągu {timeout_minutes} min")


def verdict(threshold: str = "critical") -> dict:
    response = session.get(
        f"{API_URL}/api/v1/projects/{PROJECT_ID}/ci-cd/summary",
        params={"threshold": threshold},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    upload_sources(Path("."))
    wait_for(start_analysis())

    summary = verdict()
    print(summary["description"])
    if summary["should_fail"]:
        raise SystemExit(1)
```

### JavaScript (Node.js 18+)

```javascript
/** Analiza projektu w TestGEN — od wysłania kodu po werdykt. */

import { readFile } from 'node:fs/promises';

const API_URL = 'https://api.testgen.io';
const API_KEY = 'tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';
const PROJECT_ID = '3fa85f64-5717-4562-b3fc-2c963f66afa6';

const authHeaders = { Authorization: `Bearer ${API_KEY}` };

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...authHeaders, ...(options.headers ?? {}) },
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error(`TestGEN ${response.status}: ${problem.detail ?? response.statusText}`);
  }
  return response.status === 204 ? null : response.json();
}

/** Archiwum spakuj wcześniej — upload rozpakuje je po stronie serwera. */
async function uploadSources(archivePath) {
  const form = new FormData();
  const bytes = await readFile(archivePath);
  form.append('files', new Blob([bytes], { type: 'application/zip' }), 'zrodla.zip');

  await request(`/api/v1/projects/${PROJECT_ID}/upload`, { method: 'POST', body: form });
}

async function startAnalysis() {
  const body = { engine_mode: 'native', modules: ['code_analysis', 'security_scan'] };
  const accepted = await request(`/api/v1/projects/${PROJECT_ID}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return accepted.task_id;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Odpytuje co 10 s — częściej nie ma sensu i zjada limit żądań. */
async function waitFor(taskId, timeoutMinutes = 30) {
  const deadline = Date.now() + timeoutMinutes * 60_000;
  while (Date.now() < deadline) {
    const { status, error } = await request(`/api/v1/tasks/${taskId}`);
    if (status === 'completed' || status === 'success') return;
    if (status === 'failed' || status === 'error') {
      throw new Error(`Analiza zakończona błędem: ${error ?? 'brak szczegółów'}`);
    }
    await sleep(10_000);
  }
  throw new Error(`Analiza nie zakończyła się w ciągu ${timeoutMinutes} min`);
}

async function main() {
  await uploadSources('zrodla.zip');
  await waitFor(await startAnalysis());

  const summary = await request(
    `/api/v1/projects/${PROJECT_ID}/ci-cd/summary?threshold=critical`,
  );
  console.log(summary.description);
  if (summary.should_fail) {
    process.exitCode = 1;
  }
}

await main();
```

## Częste zadania

### Pobranie przypadków testowych

Przypadki testowe są zasobem globalnym filtrowanym po projekcie, a nie
podzasobem projektu:

```bash
curl --silent --get \
  "$API_URL/api/v1/test-cases" \
  --data-urlencode "project_id=$PROJECT_ID" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=50" \
  -H "Authorization: Bearer $API_KEY" | jq '.items[] | {id, title, priority}'
```

Dostępne filtry: `project_id`, `type`, `status`, `framework`, `priority`
oraz sortowanie przez `sort_by` i `sort_order`.

### Eksport do TestRaila

```bash
curl --silent -X POST \
  "$API_URL/api/v1/projects/$PROJECT_ID/export/testrail" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"test_case_ids": []}' | jq '.'
```

Pusta lista oznacza wszystkie przypadki projektu. Eksport idzie w tle — postęp
śledzisz pod adresem z pola `status_url`. Szczegóły: [Integracja z TMS](tms-integration.md).

### Konfiguracja webhooka

```bash
curl --silent -X POST "$API_URL/api/v1/webhooks" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://twoj-system.pl/testgen-hook",
    "secret": "zmien-mnie-na-wlasny-sekret",
    "events": ["analysis.completed", "security.finding"]
  }'
```

Ta operacja wymaga **zalogowanej sesji**, nie klucza API — patrz
[Uwierzytelnianie](authentication.md#czego-kluczem-api-zrobić-nie-można).

## Interaktywna dokumentacja

W środowiskach deweloperskim i testowym dostępne są `/docs` (Swagger UI)
i `/redoc`. Każda operacja ma tam gotowe przykłady w tych samych trzech
językach, a przycisk *Authorize* pozwala wywołać endpoint wprost z przeglądarki.
W produkcji interaktywna dokumentacja jest wyłączona.

## Zobacz też

- [Uwierzytelnianie](authentication.md)
- [Limity żądań](rate-limiting.md) — obsługa `429` z kodem
- [Błędy](errors.md)
- [Referencja endpointów](endpoints/auth.md)

[↩ Powrót do spisu treści](index.md)
