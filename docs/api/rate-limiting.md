# Limity żądań

TestGEN nalicza limit **per firma**, nie per klucz API. Dziesięć kluczy nie daje
dziesięciokrotnego limitu — wszystkie dzielą ten sam kubełek, bo to firma jest
jednostką rozliczeniową.

Okno jest jednominutowe i stałe: licznik zeruje się na początku każdej minuty,
a nie po minucie od pierwszego żądania.

## Progi

| Plan | Żądań na minutę |
| --- | ---: |
| Freemium | 100 |
| Basic | 100 |
| Premium | 1000 |

Progi pochodzą z konfiguracji planów, więc źródłem prawdy pozostaje cennik.
Bieżące zużycie widać w *Panelu zużycia zasobów*.

## Nagłówki

Każda odpowiedź endpointu objętego limitem niesie trzy nagłówki:

| Nagłówek | Znaczenie |
| --- | --- |
| `X-RateLimit-Limit` | limit na minutę dla planu Twojej firmy |
| `X-RateLimit-Remaining` | ile żądań zostało w bieżącym oknie |
| `X-RateLimit-Reset` | znacznik czasu (epoch) początku następnego okna |

Warto je czytać na bieżąco zamiast czekać na `429` — `X-RateLimit-Remaining`
pozwala zwolnić tempo, zanim żądania zaczną być odrzucane.

## Przekroczenie limitu

Po wyczerpaniu kubełka API zwraca `429` z ciałem w formacie RFC 7807
i nagłówkiem `Retry-After` (liczba sekund do końca okna).

```json
{
  "type": "https://testgen.io/errors/quota-exceeded",
  "title": "Quota Exceeded",
  "status": 429,
  "detail": "Przekroczono limit żądań dla planu",
  "instance": "/api/v1/projects"
}
```

## Co jest wyłączone z limitu

Dostawy od zewnętrznych systemów i sondy zdrowia nie są liczone — to nie jest
ruch generowany przez Twoją firmę:

- `POST /api/v1/integrations/github/webhook`
- `POST /api/v1/integrations/gitlab/webhook`
- `POST /api/v1/billing/webhooks/tpay`
- `GET /api/v1/health`

Dzięki temu seria zdarzeń z jednego repozytorium nie zjada limitu przeznaczonego
na Twoje własne wywołania API.

## Zalecana obsługa

Honoruj `Retry-After` zamiast ponawiać od razu — natychmiastowe ponowienie trafi
w ten sam wyczerpany kubełek.

```python
import time

import requests


def call_with_retry(method, url, *, headers, max_attempts=4, **kwargs):
    """Wywołanie z poszanowaniem limitu TestGEN."""
    for attempt in range(1, max_attempts + 1):
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if response.status_code != 429:
            response.raise_for_status()
            return response

        # Retry-After podaje sekundy do końca bieżącego okna.
        wait = int(response.headers.get("Retry-After", 60))
        if attempt == max_attempts:
            response.raise_for_status()
        time.sleep(wait)
    raise RuntimeError("Nie udało się wykonać żądania mimo ponowień")
```

```javascript
async function callWithRetry(url, options = {}, maxAttempts = 4) {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const response = await fetch(url, options);
    if (response.status !== 429) {
      if (!response.ok) {
        throw new Error(`TestGEN API: ${response.status}`);
      }
      return response;
    }

    const wait = Number(response.headers.get('Retry-After') ?? 60);
    if (attempt === maxAttempts) {
      throw new Error('Przekroczono limit żądań — wyczerpano ponowienia');
    }
    await new Promise((resolve) => setTimeout(resolve, wait * 1000));
  }
}
```

## Jak nie dobijać do limitu

**Nie odpytuj statusu częściej niż co 10 sekund.** Analiza trwa minuty, więc
odpytywanie co sekundę zużywa limit bez żadnego zysku. Wygenerowane
konfiguracje CI/CD używają właśnie takiego odstępu.

**Zamiast odpytywania rozważ webhooki.** Zdarzenie `analysis.completed`
przychodzi samo i nie kosztuje ani jednego żądania —
patrz [Webhooki](webhooks.md).

**Wysyłaj kod jako archiwum.** Jedno żądanie z plikiem ZIP zamiast setki
osobnych uploadów; TestGEN rozpakuje je po swojej stronie.

## Zobacz też

- [Uwierzytelnianie](authentication.md)
- [Błędy](errors.md)
- [Integracja CI/CD](cicd-integration.md)

[↩ Powrót do spisu treści](index.md)
