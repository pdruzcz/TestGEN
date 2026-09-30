# Tokeny płatności, odnowienia i dunning

> Dokumentacja P2, Epic 7 — Stories 7.2, 7.4.
> Implementacja: `backend/app/services/billing/subscription_service.py`,
> `backend/app/services/billing/subscription_scheduler.py`.

## 1. Model PaymentToken

Tabela `payment_tokens` (migracja 045) — zapamiętane metody płatności
tenanta, jedna na metodę:

| Pole | Znaczenie |
|---|---|
| `kind` | `card` (token karty) / `blik` (alias BLIK Płatności Powtarzalnych) |
| `value_encrypted` | Wartość tokena zaszyfrowana per-tenant (AES; klucz pochodny z `tenant_id`) |
| `value_digest` | Skrót do wyszukiwania po wartości (indeks) — bez odszyfrowywania |
| `card_tail` / `card_brand` | Wizerunek karty do wyświetlenia (np. `4242` / Visa) |
| `expires_at` | Ważność karty / aliasu |
| `tpay_status` | Status u tpay: `active`, `pending`, `deleted`… (mapowanie `TpayTokenStatus`) |
| `is_default` | Domyślna metoda odnowień |
| `registration_id` | Id rejestracji karty (link do potwierdzenia z notyfikacji) |

Token nigdy nie jest przechowywany jawnie — odszyfrowanie
(`decrypt_token_value`) tylko na czas użycia przy obciążeniu.

## 2. Rejestracja karty bez obciążenia (Story 7.2 AC2)

`POST /api/v1/billing/payment-methods` (Owner):

1. Lokalny rekord `PaymentToken` (status `pending`) z `registration_id`.
2. `POST {TPAY_BASE_URL}/tokens` u tpay z `cliAuth` = registration_id —
   karta zapisywana jest **bez żadnego obciążenia**.
3. Odpowiedź zawiera URL przekierowania na panel tpay; po powrocie
   płatnika (`/billing/payment-methods/return`, frontend pollinguje
   potwierdzenie) i notyfikacji tokenizacji (webhook, `data.token`)
   token przechodzi w `active`.

Listę metod zwraca `GET /billing/payment-methods` — wzbogacana
odświeżeniem statusów kart u tpay (`GET /tokens/{value}`) z krótkoterminowym
cache'em 300 s; błąd dostawcy → stan lokalny (graceful degrade).
Usunięcie metody (`DELETE /billing/payment-methods/{token_id}`) woła
`DELETE /tokens/{value}` u tpay i ustawia lokalnie `tpay_status = deleted`
(soft delete). Usunięcie **jedynego aktywnego tokena przy aktywnej
subskrypcji cyklicznej → 409** (najpierw dodaj inną metodę).

## 3. Aliasy BLIK (Płatności Powtarzalne, model A)

Alias powstaje przy pierwszej płatności BLIK: checkout przekazuje tpay
wygenerowaną wartość `tg-{uuid4.hex}` (limity: pojedyncza = cena planu,
całkowita = cena × 12 płatności, ważność 730 dni, `eachMonth`).
Notyfikacje `event=ALIAS_*` (utworzenie/aktywacja/wygaśnięcie/usunięcie)
aktualizują `PaymentToken` — korelacja po `meta.blik_alias_value` z
transakcji rejestracyjnej. Limit pojedynczy gwarantuje, że odnowienie
nie obciąży więcej niż cena planu.

Jeśli bank płatnika nie obsługuje Płatności Powtarzalnych
(`refusenopayid`), checkout zwraca 422 z komunikatem — rozwiązaniem jest
płatność kartą i zapisanie jej jako metody odnowień.

## 4. Odnowienia cykliczne — scheduler 03:30

`SubscriptionScheduler.run` (Celery beat, codziennie 03:30 — po cleanupie
02:00, przed godziną szczytu; `backend/app/workers/tasks/billing_tasks.py`):

1. **Odnowienia** — subskrypcje z `next_charge_at` ≤ teraz: obciążenie
   domyślnego tokena (`transactions.py`), nowy okres
   `current_period_start/end`, `next_charge_at` + 1 miesiąc.
2. **Dunning** — nieudane obciążenie: `register_failed_charge`
   (inkrement `dunning_attempt`, `dunning_next_retry_at`),
   `_apply_dunning_downgrade` po wyczerpaniu prób.
3. **Zaplanowane downgrade** — `execute_scheduled_downgrade` dla okresów,
   które się skończyły (Story 7.5).
4. **Wygasły grace** — `enforce_grace_expiry`: subskrypcje po
   `grace_until` → ostateczny przebieg do Freemium.

Anulowana subskrypcja (`cancel_at_period_end = true`) nie generuje
obciążenia — na koniec okresu następuje powrót do Freemium (lub planu
z zaplanowanego downgrade'u, Story 7.5).

## 5. Polityka dunningu

Decyzja modelu (CR#2): dunning **zawsze prowadzi do Freemium** — konto
nie zostaje zablokowane, dane pozostają, obowiązują limity Freemium.

```
nieudane obciążenie (odnowienie)
   │  retry wg dunning_next_retry_at (ponowne próby w kolejnych dniach)
   ▼
ostateczna porażka
   │  _apply_dunning_downgrade:
   │    status=active, plan=freemium, previous_plan_id=zapisany,
   │    grace_until = teraz + DUNNING_GRACE_DAYS (7 dni)
   │    email do Ownera: _notify_downgrade (grace 7 dni)
   ▼
grace_until mija → enforce_grace_expiry (idempotentne domknięcie)
```

W ciągu 7 dni grace tenant może dobrowolnie wrócić na plan płatny
(zakup/checkout) — limity płatne obowiązują do końca grace. Po wygaśnięciu
grace obowiązują limity Freemium; powrót na plan płatny to normalny
checkout od zera.

Nieudane obciążenie z aliasu BLIK przy zaplanowanym upgrade (7.5) →
`cancel_failed_plan_change`: plan bez zmian, rekord zmiany `failed`,
email wyjaśniający.
