# Billing — moduł płatności tpay (Epic 7)

Integracja z tpay (jedyny provider — decyzja D1 z `plan-integracji-tpay.md`):
checkout redirect, tokeny kart, aliasy BLIK Płatności Powtarzalnych, webhooki.

## Webhooki — przepływ operacyjny (Story 7.3)

Endpoint: `POST /api/v1/billing/webhooks/tpay` (publiczny — autoryzacją jest
podpis **JWS** w nagłówku `X-JWS-Signature` + `md5sum` dla transakcji; tpay
nie udostępnia whitelisty IP).

Typy notyfikacji (wszystkie na ten sam URL, klasyfikacja po strukturze):

| Typ | Format | Rozpoznanie | Efekt |
|-----|--------|-------------|-------|
| transakcja | form-urlencoded | `tr_id` | logika 7.4 (paid → aktywacja, chargeback → ręczna weryfikacja) |
| alias BLIK | form-urlencoded | `event=ALIAS_*` + `msg_value[value]` | aktualizacja `PaymentToken` (status/ważność) |
| tokenizacja | JSON | `type=tokenization\|token_update`, `data.token` | zapis tokena karty (serwis 7.2) |
| inne | dowolny | — | audyt `skipped`, odpowiedź TRUE |

Semantyka odpowiedzi (AC5): sukces/pomijanie → **200** (`TRUE` / `{"result":true}`);
błąd walidacji → **400** (bez ponowień); wyjątek przetwarzania → **5xx**
(tpay ponawia: próby 1–10 co 1 min, 11–20 co 3 min, … do 37; 404 przerywa).
Idempotencja po `event_uid` chroni przed podwójnym przetworzeniem przy ponowieniach.

Korelacja alias→tenant: checkout generuje wartość aliasu (`tg-{uuid4.hex}`),
przekazuje ją tpay w `blikPaymentData.aliases[0].value` i zapisuje w
`PaymentTransaction.meta.blik_alias_value` — notyfikacje `ALIAS_*` dopasowują
tenanta dokładnie po tej wartości.

### Monitoring (AC6)

- **Metryki Prometheus** (`/metrics`): `webhook_processed_total{provider,type,status}`,
  `webhook_processing_seconds` (histogram).
- **Health panelu admina**: `GET /api/v1/billing/webhooks/health` (rola admin) —
  liczniki przetworzonych/odrzuconych/pominiętych, `last_success_age_seconds`,
  `consecutive_failures` + flaga `alert` (>3 kolejne porażki).
- **Reguła alertu** (>3 kolejne nieudane przetworzenia w 5 min) — do wklejenia
  w Prometheus/alertmanager (infrastruktura serwera, poza repo):

  ```yaml
  groups:
    - name: billing-webhooks
      rules:
        - alert: TpayWebhookProcessingFailing
          expr: increase(webhook_processed_total{status="error"}[5m]) > 3
          for: 0m
          labels:
            severity: warning
          annotations:
            summary: "tpay webhooki — seria nieudanych przetworzeń"
            description: "Więcej niż 3 nieudane przetworzenia w 5 min. Sprawdź /api/v1/billing/webhooks/health i logi backendu (tpay webhook)."
  ```

### Właściciel procesu alertów tpay

**Piotr Decyk** — alerty tpay o nieudanych próbach dostarczenia notyfikacji
(wysyłane przez tpay na skrzynkę sprzedawcy **testgen@nexio.pl** po 3 nieudanych
próbach) trafiają do niego. Procedura reakcji:

1. Sprawdź `GET /api/v1/billing/webhooks/health` (liczniki, seria porażek).
2. Przejrzyj `webhook_events` (statusy `error`/`rejected_*`) i logi backendu
   (`tpay webhook` — pełne stack trace'e przy `error`).
3. Awaria przejściowa (np. baza) → tpay ponawia automatycznie do 37 prób —
   zwykle samo się wyrabia; obserwuj `consecutive_failures` aż wróci 0.
4. Rozjazd stanu (np. po dłuższej awarii) → replay przez
   `POST /api/v1/admin/billing/webhooks/{event_uid}/replay` (rola admin,
   wpis w audycie admina; niedostępny dla zdarzeń odrzuconych walidacją).
5. Trwały błąd walidacji (całkiem odrzucane) → sprawdź rotację certyfikatów
   JWS (cache odświeża się przy niedopasowaniu; TTL 24 h) i `TPAY_SECURITY_CODE`.

### Replay (AC7)

`POST /api/v1/admin/billing/webhooks/{event_uid}/replay` — ponowne
przetworzenie zapisanego `WebhookEvent.raw` tym samym pipeline'em (pominięta
walidacja — dane pochodzą z audytu; zdarzenia `rejected_*` nie podlegają
replay). Operacja logowana w audycie admina; idempotencja biznesowa
(`event_uid` → `processed`) zapobiega podwójnym efektom.

## Migracje

- `044` — `payment_transactions`, `webhook_events` (7.4)
- `045` — `payment_tokens`, dunning subskrypcji (7.2)
- `046` — `webhook_events.error_message` (7.3)
