# Webhooki tpay

> Dokumentacja P2, Epic 7 — Stories 7.3, 7.4.
> Implementacja: `backend/app/services/billing/webhook_processor.py`,
> `backend/app/api/routes/webhooks_tpay.py`.
> Operacyjny przegląd: `backend/app/services/billing/README.md`.

## 1. Endpoint i autoryzacja

`POST /api/v1/billing/webhooks/tpay` — **publiczny** (bez JWT). Autoryzacją
jest podpis notyfikacji:

- **JWS** w nagłówku `X-JWS-Signature` (detached payload) — notyfikacje
  JSON i form-urlencoded; certyfikat x509 pobierany z `TPAY_JWS_CERT_URL`
  i cache'owany (TTL 24 h, odświeżenie przy niedopasowaniu).
- **md5sum** — dodatkowo dla notyfikacji transakcyjnych; wzór zaczyna się
  od `TPAY_MERCHANT_ID` i zawiera `TPAY_SECURITY_CODE`.

tpay nie udostępnia whitelisty IP — podpis jest jedyną linią obrony;
wszystkie notyfikacje (także odrzucone) są audytowane w `webhook_events`
(commit audytu także przy 400/500).

## 2. Macierz typów notyfikacji

Wszystkie typy trafiają na ten sam URL; klasyfikacja po strukturze
(`WebhookProcessor._classify`):

| Typ | Format | Rozpoznanie | Efekt |
|-----|--------|-------------|-------|
| Transakcja | form-urlencoded | `tr_id` | logika 7.4: `paid` → `mark_paid` (aktywacja/odnowienie planu, faktura), chargeback → ręczna weryfikacja |
| Alias BLIK | form-urlencoded | `event=ALIAS_*` + `msg_value[value]` | aktualizacja `PaymentToken` (status/ważność) po dopasowaniu aliasu |
| Tokenizacja | JSON | `type=tokenization\|token_update`, `data.token` | zapis/aktualizacja tokena karty (serwis 7.2) |
| Inne | dowolny | — | audyt `skipped`, odpowiedź TRUE |

Korelacja alias→tenant: checkout zapisuje wartość aliasu w
`PaymentTransaction.meta.blik_alias_value`; notyfikacje `ALIAS_*`
dopasowują tenanta po tej wartości (`find_blik_alias_token`).

## 3. Semantyka odpowiedzi

| Wynik | HTTP | Body | tpay |
|---|---|---|---|
| Sukces / pominięcie (idempotencja, nieobsługiwany typ, brak dopasowania) | 200 | `TRUE` (form) / `{"result":true}` (JSON) | przerywa serię ponowień |
| Błąd walidacji (JWS/md5/śmieciowy payload) | 400 | `FALSE` | **bez ponowień** |
| Wyjątek przetwarzania (np. baza) | 5xx | `FALSE` | ponawia wg harmonogramu |

Harmonogram ponowień tpay: próby 1–10 co 1 min, 11–20 co 3 min, dalej
rzadziej — do 37 prób; HTTP 404 przerywa serię. **Idempotencja po
`event_uid`** chroni przed podwójnym przetworzeniem tej samej notyfikacji
przy ponowieniach.

`event_uid` jest deterministyczny per typ i treść notyfikacji — replika
notyfikacji trafia na istniejący rekord `webhook_events` i zwraca sukces
bez ponownych efektów ubocznych.

## 4. Efekty transakcji (mark_paid)

`WebhookProcessor.mark_paid` dla transakcji `paid`:

1. `PaymentTransaction.status = paid` (+ `paid_amount`, `test_mode`).
2. Aktywacja planu: pierwszy zakup → `activate_paid_plan`; odnowienie →
   przesunięcie okresu; upgrade z `meta.plan_change_id` →
   `finalize_plan_upgrade` (Story 7.5).
3. Faktura VAT: `InvoiceService.generate_invoice` (idempotentna po
   `payment_id`) → PDF → MinIO → email z załącznikiem (szczegóły:
   [09 — Faktury VAT](09-faktury-vat.md)).
4. Email potwierdzenia zakupu do płatnika.

Nieudane obciążenie cykliczne (`tr_status` FALSE przy odnowieniu) →
`_handle_recurring_declined` → rejestracja porażki w dunningu
(szczegóły: [05 — Tokeny i odnowienia](05-tokeny-i-odnowienia.md)).
Porównanie `tr_status` jest bezrolkowe (TRUE/FALSE).

## 5. Monitoring (Story 7.3 AC6)

- **Prometheus** (`/metrics`): licznik `webhook_processed_total{provider,type,status}`,
  histogram `webhook_processing_seconds`.
- **Health panelu admina**: `GET /api/v1/billing/webhooks/health` (rola
  admin) — liczniki przetworzonych/odrzuconych/pominiętych,
  `last_success_age_seconds`, `consecutive_failures`, flaga `alert`
  (>3 kolejne porażki).
- **Reguła alertu** Prometheus (>3 nieudane przetworzenia w 5 min):
  konfiguracja w `backend/app/services/billing/README.md`.

Alerty tpay o nieudanych próbach dostarczenia (skrzynka sprzedawcy
testgen@nexio.pl po 3 nieudanych próbach) trafiają do właściciela procesu.
Procedura reakcji (5 kroków): health → `webhook_events` i logi → obserwacja
`consecutive_failures` (tpay ponawia sam) → replay → kontrola rotacji
certyfikatów JWS i `TPAY_SECURITY_CODE`.

## 6. Replay (Story 7.3 AC7)

`POST /api/v1/admin/billing/webhooks/{event_uid}/replay` — rola admin,
wpis w audycie admina. Ponownie przetwarza zapisany `WebhookEvent.raw`
tym samym pipeline'em (walidacja pominięta — dane pochodzą z audytu).
Zdarzenia odrzucone walidacją (`rejected_*`) nie podlegają replayowi;
idempotencja biznesowa (`event_uid` → `processed`) zapobiega podwójnym
efektom. Użycie: rozjazd stanu po dłuższej awarii (np. baza niedostępna
w czasie ponowień tpay).
