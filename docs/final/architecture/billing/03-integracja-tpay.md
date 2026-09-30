# Integracja tpay — checkout

> Dokumentacja P2, Epic 7 — Stories 7.4, 7.2, 7.3.
> Implementacja: `backend/app/services/billing/providers/tpay/`,
> `backend/app/api/routes/billing.py` (POST `/billing/checkout`).
> Plan integracji: `_bmad-output/planning-artifacts/plan-integracji-tpay.md`.

## 1. Decyzje architektoniczne

- **D1 — jedyny provider**: tpay zastępuje Stripe + Przelewy24 (change
  request PRD FR56, 2026-08-28). Abstrakcja `PaymentProvider`
  (`providers/base.py`) pozwala w przyszłości dodać kolejnych dostawców,
  ale obecnie jedyna implementacja to `TpayProvider`.
- **D2 — minimalna powierzchnia API**: platforma nie robi obciążeń
  bezpośrednich; każdy przelew pieniędzy odbywa się w Panelu Transakcyjnym
  tpay (redirect), a stan jest aktualizowany webhookiem. Podgląd proration
  i operacje anulowania liczone są lokalnie, bez wywołań tpay.
- Sekrety (`TPAY_CLIENT_SECRET`, `TPAY_SECURITY_CODE`) wyłącznie z
  env/secrets; rotacja + monitorowanie użycia (wymóg tpay).

## 2. Klient Open API

`providers/tpay/`:

| Plik | Odpowiedzialność |
|---|---|
| `auth.py` | Token OAuth (client credentials) dla Open API |
| `client.py` | Wspólny klient HTTP, obsługa błędów `TpayApiError` |
| `transactions.py` | `POST /transactions` (utworzenie transakcji), `GET /transactions/{id}` (reconciliation) |
| `tokens.py` | `POST /tokens` (rejestracja karty), `GET /tokens/{value}` (status), `DELETE /tokens/{value}` |
| `webhooks.py` | Weryfikacja podpisu notyfikacji (JWS + md5sum) — szczegóły: [04 — Webhooki](04-webhooki.md) |

Środowiska: `TPAY_ENV=sandbox` → `https://openapi.sandbox.tpay.com`,
`production` → `https://api.tpay.com` (nadpisywane przez `TPAY_BASE_URL`).

Grupy płatności Panelu Transakcyjnego: **150 = BLIK**, **103 = karta**
(`TPAY_GROUP_ID_BLIK` / `TPAY_GROUP_ID_CARD`). Płatnik wybiera metodę
(BLIK, karta z 3DS, przelew/PBL) już w panelu tpay.

## 3. Przepływ checkoutu (Story 7.4)

`POST /api/v1/billing/checkout` — wymaga roli **Owner**:

1. **Guard 409** — tenant z aktywnym planem płatnym nie kupuje ponownie;
   zmiana planu wyłącznie przez `POST /subscription/change` (Story 7.5).
2. **Rekord lokalny** — `PaymentTransaction` (status `pending`) z
   `hidden_description` = `order_id` (UUID — webhook koreluje transakcję
   po polu `tr_crc`) i `meta`: plan, dane płatnika, `blik_alias_value`.
3. **Alias BLIK** — checkout generuje wartość aliasu `tg-{uuid4.hex}`
   (model A Płatności Powtarzalnych PAYID, Story 7.3 AC3) i przekazuje ją
   tpay w `blikPaymentData.aliases[0].value`. Notyfikacje `ALIAS_*`
   dopasowują tenanta **dokładnie** po tej wartości zapisanej w
   `PaymentTransaction.meta.blik_alias_value`.
4. **Wywołanie tpay** — `POST {TPAY_BASE_URL}/transactions` z kwotą z env,
   opisem „TestGEN — subskrypcja {Plan} (miesięczna)", danymi płatnika
   i URL-ami powrotu.
5. **Odpowiedź** — `order_id`, `transaction_id` i
   `transaction_payment_url`; frontend przekierowuje płatnika na panel tpay.

Limity aliasu BLIK (konfiguracja): płatność pojedyncza = cena planu,
limit całkowity = cena × `TPAY_BLIK_ALIAS_TOTAL_LIMIT_PAYMENTS` (12),
ważność `TPAY_BLIK_ALIAS_EXPIRATION_DAYS` (730 dni), częstotliwość
`eachMonth`.

### Obsługa błędów checkoutu

| Sytuacja | Status | Zachowanie |
|---|---|---|
| Aktywny plan płatny | 409 | Skieruj na `/subscription/change` |
| `refusenopayid` od tpay | 422 | Bank płatnika nie obsługuje Płatności Powtarzalnych BLIK — komunikat z sugestią płatności kartą i zapisania jej jako metody (Story 7.2 AC7) |
| Błąd API tpay / wyjątek | 502 | Rekord pending wycofany (rollback), płatnik może ponowić |

## 4. Strony powrotu i status transakcji

Konfiguracja URL-i (env): `TPAY_SUCCESS_URL` → `/billing/checkout/success`,
`TPAY_ERROR_URL` → `/billing/checkout/error`, rejestracja karty:
`TPAY_PAYMENT_METHODS_RETURN_URL` → `/billing/payment-methods/return`.

Strony powrotu odpytują `GET /api/v1/billing/transactions/{order_id}`
(polling do rozstrzygnięcia statusu). Gdy lokalny status wisi na `pending`
dłużej niż próg, endpoint robi **jednorazowy** fallback reconciliation
`GET /transactions/{id}` u tpay — okresowy polling transakcji jest
wzbroniony wymogami tpay. Rozbieżności między stanem lokalnym a tpay
są logowane jako alerty.

Ostatecznym źródłem prawdy o płatności jest **webhook** (aktywacja planu
następuje w `mark_paid`, nie na stronie powrotu) — szczegóły:
[04 — Webhooki](04-webhooki.md).

## 5. Środowisko sandbox

Runbook: `docs/final/troubleshooting/tpay-sandbox-runbook.md` — konto sandbox, kwoty
sterujące scenariuszami płatności (`scripts/set_sandbox_prices.py`),
14 scenariuszy GUI happy-path i błędów. W sandboxu weryfikacja podpisu
JWS korzysta z certyfikatu z nagłówka `x5u` — szczegóły w rozdziale
webhooków.
