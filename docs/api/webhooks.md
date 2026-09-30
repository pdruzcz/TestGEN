# Webhooki

TestGEN powiadamia Twoje systemy o ważnych zdarzeniach, wysyłając `POST` pod
skonfigurowany adres. To odwrotność integracji z GitHubem i GitLabem — tam
TestGEN odbiera zdarzenia, tu je wysyła.

Webhooki konfiguruje się w *Ustawienia → Webhooki* albo przez API
(`POST /api/v1/webhooks`). Założenie webhooka wymaga roli właściciela firmy
i zalogowanej sesji — kluczem API tej operacji wykonać się nie da.

## Kształt dostawy

```http
POST /twoj-endpoint HTTP/1.1
Content-Type: application/json
User-Agent: TestGEN-Webhook/1.0
X-TestGEN-Event: analysis.completed
X-TestGEN-Delivery: 7c9e6679-7425-40de-944b-e07fc1f90ae7
X-TestGEN-Signature: sha256=8f4a1c...
```

| Nagłówek | Znaczenie |
| --- | --- |
| `X-TestGEN-Event` | typ zdarzenia |
| `X-TestGEN-Delivery` | identyfikator dostawy — klucz idempotencji |
| `X-TestGEN-Signature` | `sha256=` + HMAC‑SHA256 ciała, podpisany Twoim sekretem |

Każde ciało zawiera co najmniej `event_type` i `timestamp` (ISO 8601, UTC);
pozostałe pola zależą od zdarzenia.

## Weryfikacja podpisu

**Licz HMAC nad surowymi bajtami ciała, dokładnie tak, jak przyszły.**
To najczęstsza przyczyna nieudanej weryfikacji: sparsowanie JSON‑a i ponowne
złożenie go do tekstu zmienia kolejność kluczy albo separatory, więc podpis
przestaje się zgadzać. Większość frameworków webowych udostępnia surowe ciało
osobno od sparsowanego.

Porównuj podpisy funkcją stałoczasową (`hmac.compare_digest`,
`crypto.timingSafeEqual`). Zwykłe `==` kończy się na pierwszym różniącym
bajcie i zdradza atakującemu, ile znaków trafił.

### Python (Flask)

```python
import hashlib
import hmac

from flask import Flask, request, abort

app = Flask(__name__)
SECRET = "twoj-sekret-z-konfiguracji-webhooka"


def signature_ok(raw_body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256=") :])


@app.post("/testgen-hook")
def testgen_hook():
    # request.data to surowe bajty — nie używaj request.get_json() do podpisu.
    if not signature_ok(request.data, request.headers.get("X-TestGEN-Signature")):
        abort(401)

    event = request.headers.get("X-TestGEN-Event")
    delivery_id = request.headers.get("X-TestGEN-Delivery")
    payload = request.get_json()

    handle(event, delivery_id, payload)
    return "", 204
```

### JavaScript (Express)

```javascript
const crypto = require('node:crypto');
const express = require('express');

const app = express();
const SECRET = 'twoj-sekret-z-konfiguracji-webhooka';

// express.raw() zachowuje surowe bajty — express.json() by je stracił.
app.post('/testgen-hook', express.raw({ type: 'application/json' }), (req, res) => {
  const header = req.get('X-TestGEN-Signature') ?? '';
  const expected =
    'sha256=' + crypto.createHmac('sha256', SECRET).update(req.body).digest('hex');

  const a = Buffer.from(header);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    return res.sendStatus(401);
  }

  const payload = JSON.parse(req.body.toString('utf8'));
  handle(req.get('X-TestGEN-Event'), req.get('X-TestGEN-Delivery'), payload);
  res.sendStatus(204);
});
```

## Typy zdarzeń

### `analysis.completed`

Analiza projektu zakończona.

```json
{
  "event_type": "analysis.completed",
  "timestamp": "2026-01-15T10:00:00+00:00",
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "task_id": "c0ffee00-1234-4abc-8def-0123456789ab",
  "status": "completed",
  "summary": {
    "steps_completed": 6,
    "steps_total": 6,
    "test_cases_generated": 42
  }
}
```

`status` przyjmuje `completed` albo `partial_failure` — to drugie znaczy, że
analiza się skończyła, ale część kroków nie powiodła się.

### `security.finding`

Wykryta podatność o wadze `critical` albo `high`. Niższe wagi nie generują
zdarzeń — webhook ma budzić dyżur, a nie zalewać go szumem, który i tak
przejrzy się w raporcie. Zdarzenie powstaje osobno dla każdego znaleziska.

```json
{
  "event_type": "security.finding",
  "timestamp": "2026-01-15T10:02:13+00:00",
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "finding_id": "9a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
  "severity": "critical",
  "type": "SQL Injection",
  "description": "Parametr zapytania trafia do zapytania SQL bez parametryzacji",
  "file_path": "app/repository/users.py",
  "line": 118
}
```

### `gap.detected`

Wykryta luka funkcjonalna — rozbieżność między dokumentacją a kodem.
Zdarzenie jest wysyłane raz na analizę i opisuje pierwszą lukę oraz ich
łączną liczbę.

```json
{
  "event_type": "gap.detected",
  "timestamp": "2026-01-15T10:05:41+00:00",
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "gap_id": "2b7d1f90-3c4a-4b5c-9d8e-7f6a5b4c3d2e",
  "type": "missing",
  "requirement": "FR-18",
  "description": "Wymaganie „eksport do CSV” nie ma odpowiednika w kodzie",
  "total_findings": 7
}
```

### `export.ready`

Raport wygenerowany i gotowy do pobrania.

```json
{
  "event_type": "export.ready",
  "timestamp": "2026-01-15T10:09:02+00:00",
  "export_id": "5d4c3b2a-1f0e-4d9c-8b7a-6e5d4c3b2a1f",
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "format": "pdf",
  "filename": "raport_3fa85f64_20260115_100902.pdf",
  "download_url": "https://api.testgen.io/api/v1/exports/5d4c3b2a-1f0e-4d9c-8b7a-6e5d4c3b2a1f/download"
}
```

`download_url` wymaga uwierzytelnienia — to endpoint TestGEN, nie bezpośredni
link do magazynu plików.

### `subscription.changed`

Zmiana planu subskrypcji — po opłaconym podwyższeniu albo po wykonaniu
zaplanowanego obniżenia.

```json
{
  "event_type": "subscription.changed",
  "timestamp": "2026-01-15T00:00:05+00:00",
  "old_plan": "basic",
  "new_plan": "premium",
  "effective_date": "2026-01-15T00:00:00+00:00"
}
```

## Ponowienia

Dostawa uznana za nieudaną (przekroczenie 10 sekund, kod `5xx`, błąd sieci)
jest ponawiana **trzy razy**, z narastającym odstępem:

| Próba | Kiedy |
| :-: | --- |
| 1 | natychmiast |
| 2 | po 1 minucie |
| 3 | po 5 minutach |
| 4 | po 30 minutach |

Odpowiedź `2xx` na dowolnej próbie kończy dostawę powodzeniem. Po wyczerpaniu
prób dostawa jest oznaczana jako nieudana, a operacja trafia do dziennika
audytu. Historia wszystkich prób — z kodem odpowiedzi i fragmentem ciała —
jest widoczna w *Ustawienia → Webhooki → Historia dostaw* i przez
`GET /api/v1/webhooks/{id}/deliveries`.

Odpowiadaj szybko. TestGEN czeka 10 sekund; jeśli Twoja obsługa zdarzenia trwa
dłużej, zwróć `2xx` od razu i wykonaj pracę w tle.

## Idempotencja

Ponowienie wysyła **ten sam** `X-TestGEN-Delivery`. Jeśli Twój endpoint zdążył
przetworzyć zdarzenie, ale odpowiedź nie dotarła, dostaniesz je ponownie z tym
samym identyfikatorem.

Zapisuj identyfikatory obsłużonych dostaw i pomijaj powtórki:

```python
def handle(event: str, delivery_id: str, payload: dict) -> None:
    if already_processed(delivery_id):   # np. SETNX w Redisie z TTL 7 dni
        return
    process(event, payload)
    mark_processed(delivery_id)
```

## Obsługa błędów po Twojej stronie

| Sytuacja | Co zwrócić | Co zrobi TestGEN |
| --- | --- | --- |
| zdarzenie obsłużone | `200`–`204` | oznaczy dostawę jako dostarczoną |
| zdarzenie nieznane / nieinteresujące | `200` | to samo — nie ponowi |
| chwilowa awaria po Twojej stronie | `503` | ponowi wg harmonogramu |
| zły podpis (u Ciebie) | `401` | ponowi, a po wyczerpaniu prób oznaczy jako nieudaną |

Nie zwracaj `4xx` dla zdarzeń, których nie chcesz obsługiwać — lepiej odfiltruj
je po stronie konfiguracji webhooka, subskrybując tylko potrzebne typy.

## Sekret

Sekret ma co najmniej 16 znaków i jest przechowywany w TestGEN w postaci
zaszyfrowanej. Nie wraca żadnym endpointem — Twoja kopia jest jedyną, którą
masz. Zmiana sekretu jest natychmiastowa: kolejne dostawy będą podpisane nowym.

Adres endpointu musi używać HTTPS. Podpis uwierzytelnia nadawcę, ale nie
szyfruje treści, a payload niesie dane Twoich analiz.

## Zobacz też

- [Endpointy: webhooki](endpoints/webhooks.md) — pełna referencja API
- [Limity żądań](rate-limiting.md) — webhooki jako alternatywa dla odpytywania
- [Uwierzytelnianie](authentication.md)

[↩ Powrót do spisu treści](index.md)
