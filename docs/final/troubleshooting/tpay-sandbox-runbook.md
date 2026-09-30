# Runbook: weryfikacja integracji tpay na środowisku testowym (sandbox)

> Story 7.12 — macierz scenariuszy płatności. Ten dokument to **instrukcja
> ręcznej weryfikacji na prawdziwym sandboxie tpay** (GUI + skrypty):
> pozytywne ścieżki ORAZ poprawna obsługa błędów. Odpowiednik automatyczny
> (mocki): `backend/tests/scenarios/` + `backend/tests/integration/test_tpay_sandbox.py`
> (marker `tpay_sandbox`). Dane sterujące: §2.1 planu integracji tpay
> (`_bmad-output/planning-artifacts/plan-integracji-tpay.md`).

## 0. Warunki wstępne (jednorazowo)

1. **Środowisko**: `https://testgen.nexio.pl` (serwer 10.0.3.22, Docker
   Compose), backend z env: `TPAY_ENV=sandbox` + `TPAY_CLIENT_ID` /
   `TPAY_CLIENT_SECRET` / `TPAY_SECURITY_CODE` / `TPAY_MERCHANT_ID`.
2. **Panel tpay (sandbox)** — Ustawienia → Powiadomienia:
   - URL notyfikacji: `https://testgen.nexio.pl/api/v1/billing/webhooks/tpay`
   - zaznaczone **„Zezwól na nadpisanie adresu URL powiadomienia"**
     (wymagane dla notyfikacji aliasów BLIK).
3. **Konto testowe**: tenant z rolą **Owner** (checkout/zmiana planu wymaga
   Ownera; nowy tenant startuje na Freemium — idealny punkt wyjścia).
4. **Nawigacja**: menu **Rozliczenia** w navbarze (Plany subskrypcji, Zużycie
   zasobów, Faktury; Owner dodatkowo: Dane fakturowe, Metody płatności).

## 1. Zasada sterowania scenariuszami: KWOTA = przełącznik sandboxa

Sandbox tpay reaguje na kwotę transakcji, a kwota checkoutu = cena planu z
env (`BILLING_BASIC_MONTHLY_PRICE` / `BILLING_PREMIUM_MONTHLY_PRICE`).
Skrypt [`backend/scripts/set_sandbox_prices.py`](../../../backend/scripts/set_sandbox_prices.py)
podmienia cenę w `.env`; DB synchronizuje się seedem przy restarcie.

```bash
# na serwerze testowym (w katalogu z docker-compose; dostosuj ścieżkę .env)
docker compose exec backend python scripts/set_sandbox_prices.py --list          # dostępne scenariusze
docker compose exec backend python scripts/set_sandbox_prices.py --scenario frictionless
docker compose up -d backend            # restart = seed synchronizuje DB
# weryfikacja nowej ceny:
curl -s https://testgen.nexio.pl/api/v1/billing/plans -H "Authorization: Bearer <JWT>" | jq '.plans[].price_monthly'
```

**Po każdej zmianie scenariusza**: restart backendu + odśwież stronę planów
(cena na karcie planu musi pokazywać kwotę sterującą). Po testach:
`--reset` (Basic 30.00 / Premium 50.00).

> Kwoty sterujące NIE są cenami produktu (§3.2a) — to przełączniki testowe.

## 2. Dane płatnicze sandbox (Panel Transakcyjny tpay)

| Co | Wartość | Uwagi |
|---|---|---|
| Kod BLIK | `777123` (dowolne `777xxx`) | poprawny kod |
| Karty | `2223 0002 8000 0016` (MC), `4056 2178 4359 7258` (Visa) | CVC: 3 dowolne cyfry; data: przyszła |
| Grosze 3DS | `.01` frictionless, `.03` sukces, `.05` błąd 3DS, `.06` decline, inne → challenge | kwota końcówka steruje |
| Błędy kart | `500.00` / `501.00` / `503.00` (+`504.00` tylko token) | |
| Błędy BLIK | `144.00` płatnik, `168.00` wystawca, `120.00` brak środków, `312.00` timeout, `96.00` limit, `216.00` bezpieczeństwo | |
| Alias PAYID | grosze `.08`–`.15` | alias żyje ≥ tydzień; kody `999xxx` czyszczone co 15 min — nie polegać |
| Bank bez PP | `495.00` | refuseNoPayId → nasze 422 |

## 3. Scenariusze

Legenda weryfikacji: **GUI** (co widzi tester), **DB** (SQL — patrz §4),
**API** (`curl`/strona), **EMAIL** — w sandboxie maile do płatników są
zablokowane (§4.4 planu): potwierdzenia sprawdzamy w logach backendu
(`docker compose logs backend | grep -i email` — żądania wysyłki) lub
pomijamy.

Przed KAŻDYM scenariuszem zakupu tenant powinien być na **Freemium**
(po porażce zostaje Freemium — można kontynuować; po sukcesie — patrz §5 reset).

---

### S1. Zakup planu Basic kodem BLIK — pozytywna ścieżka (AC1)

**Przygotowanie**: `--scenario happy` (cena neutralna 30.00) + restart.

1. GUI: **Rozliczenia → Plany subskrypcji**; karta **Basic** → **Wybierz Basic**.
2. Strona „Przekierowanie do płatności" → automatyczny redirect na Panel
   Transakcyjny tpay (kwota 30.00, opis „TestGEN — subskrypcja Basic (miesięczna)").
3. Na panelu tpay: wybierz **BLIK**, wpisz `777123`, zatwierdź.
4. Powrót na `https://testgen.nexio.pl/billing/checkout/success?...` — strona
   potwierdzenia (polling statusu → „opłacona").

**Oczekiwane (poprawność = FAIL, jeśli brak)**:
- GUI: plan aktualny = Basic (karta planów podświetla), liczniki w
  **Zużycie zasobów** liczą się od 0 (nowy okres).
- DB: `payment_transactions.status = 'paid'`, `test_mode = true`;
  `subscriptions.status = 'active'`, `next_charge_at = current_period_end`.
- Faktura: **Rozliczenia → Faktury** — pozycja z bieżącego dnia (PDF po chwile,
  generuje Celery; brak PDF = jeszcze nie wygenerowany, nie błąd).

### S2. Zakup kartą z zapisem metody — pozytywna + token (AC2)

**Przygotowanie**: `--scenario happy` + restart; tenant Freemium.

1. **Rozliczenia → Plany subskrypcji** → **Wybierz Basic**.
2. Na panelu tpay: metoda **karta**, dane `2223 0002 8000 0016`, CVC `123`,
   data `12/30`; **zaznacz „zapamiętaj kartę"** (save=1).
3. (3DS challenge może się pojawić przy tej kwocie — potwierdź go.)
4. Powrót na stronę potwierdzenia.

**Oczekiwane**:
- **Rozliczenia → Metody płatności**: karta `•••• 0016 mastercard`, status
  aktywna, **domyślna** (odnowienia będą obciążać tę kartę).
- DB: `payment_tokens` (kind `card_token`, `tpay_status='active'`),
  `subscriptions.payment_token_id` ustawione.

### S3. Zakup przelewem bankowym (PBL) — pozytywna (AC3)

**Przygotowanie**: `--scenario happy --plan premium` + restart.

1. Plany → **Wybierz Premium**; na panelu tpay: metoda **przelew**,
   wybierz dowolny bank z listy sandbox; opłać symulowanie.
2. Powrót na stronę potwierdzenia.

**Oczekiwane**: jak S1 (plan Premium, faktura). Uwaga: notyfikacja tpay nie
niesie kanału płatności — „przelew" nie jest odrębnym polem w historii
(ograniczenie u źródła, patrz README scenariuszy).

### S4. 3DS sterowany groszami — 5 wariantów (AC4)

Dla każdego wariantu: ustaw scenariusz + restart + zakup Basic (S1 kroki),
zapłać kartą `2223 0002 8000 0016`:

| Wariant | Skrypt (`--scenario`) | Kwota | Na paneli tpay | Oczekiwany wynik w TestGEN |
|---|---|---|---|---|
| frictionless | `frictionless` | 30.01 | brak 3DS, od razu success | success, plan aktywny |
| sukces 3DS | `threeds_success` | 30.03 | challenge → potwierdź | success, plan aktywny |
| **błąd 3DS** | `threeds_error` | 30.05 | challenge → błąd | strona `/billing/checkout/error` z komunikatem + **przycisk ponowienia**; tenant nadal Freemium; nowy checkout możliwy |
| **decline** | `decline` | 30.06 | odmowa bez 3DS | jw. |
| challenge | `challenge` | 30.02 | challenge → potwierdź | success, plan aktywny |

**Obsługa błędów — asercje**: strona błędu pokazuje status „nieopłacona",
CTA ponowienia wraca na plany; DB: transakcja bez `paid`; subskrypcja
niedotknięta (Freemium).

### S5. Błędy kart — kwoty wymuszające (AC5)

Warianty: `card_error_500` / `card_error_501` / `card_error_503` (`card_error_504`
dotyczy obciążenia tokenem — patrz S10). Krok jak S4 (karta, kwota sterująca):
panel tpay zwraca błąd → strona błędu TestGEN + ponowienie. Tenant zostaje
na planie wyjściowym.

### S6. Błędy BLIK — 6 kwot (AC5)

Warianty: `blik_rejected_by_payer` (144), `blik_rejected_by_issuer` (168),
`blik_no_funds` (120), `blik_timeout` (312), `blik_limit` (96),
`blik_security` (216). Krok jak S1, ale BLIK `777123` na kwocie sterującej:
odmowa → strona błędu + ponowienie; tenant Freemium; **powiadomienie
o nieudanej płatności** widoczne w logach email.

### S7. Bank bez Płatności Powtarzalnych — refuseNoPayId (AC10)

**Przygotowanie**: `--scenario refuse_no_payid` (495.00) + restart.

1. Plany → **Wybierz Basic**.

**Oczekiwane**: backend dostaje od tpay `refuseNoPayId` już przy tworzeniu
transakcji → GUI pokazuje **422** z komunikatem PL: „Twój bank nie obsługuje
płatności powtarzalnych BLIK… Zapłać kartą i zapisz ją jako metodę płatności…"
+ powrót do planów. (Jeśli sandbox odmawia tylko przy opisie `mock`,
potwierdź wariant API: `tests/integration/test_tpay_sandbox.py` →
`test_bank_without_repeatable_payments_refuses_payid`.)

### S8. Upgrade Basic → Premium z proration (AC6)

**Przygotowanie**: tenant na Basic (po S1), `--reset` + restart (ceny 30/50).

1. **Rozliczenia → Plany subskrypcji**; na karcie Premium akcja zmiany planu.
2. **Dialog potwierdzenia** zmiany planu pokazuje **kwotę prorated**
   (liczoną lokalnie: `((50-30)/dni okresu) × pozostałe dni`) — zweryfikuj
   z podglądem proration na tym samym dialogu (spójność preview↔charge).
3. Zapisana karta z S2 → obciążenie bez redirectu; inaczej checkout z kwotą
   prorated.
4. Po `paid`: plan Premium natychmiast.

**Oczekiwane**: GUI — aktualny plan Premium; **Zużycie zasobów** — limity
Premium (analizy bez limitu), **liczniki zachowane** (nie zerują);
DB: `plan_change_history` (upgrade, `completed`, `proration_details.amount`).

### S9. Odnowienie aliasem BLIK PAYID — bez udziału użytkownika (AC10)

**Przygotowanie**: `--scenario payid_alias` (30.08) + restart; tenant Freemium.

1. Zakup Basic jak S1, ale na panelu tpay: BLIK `777123` **+ zaznacz zgodę
   na Płatności Powtarzalne (alias)**. Kwota 30.08 ∈ x.08–x.15 → alias
   zostaje zarejestrowany.
2. Weryfikacja: **Metody płatności** — pozycja „alias BLIK (PAYID)"; DB:
   `payment_tokens.kind = 'blik_alias_payid'`, status aktywny.
3. Wymuś wymagalność odnowienia (skróć okres — SQL §4.3), potem jednorazowy
   przebieg schedulera:
   ```bash
   docker compose exec backend python scripts/run_billing_scheduler.py
   ```
4. Na panelu tpay zatwierdź obciążenie merchant-initiated (sandbox może
   wymagać akceptacji płatnika) → webhook `paid`.

**Oczekiwane**: odnowienie bez logowania użytkownika do panelu TestGEN;
DB: nowa transakcja `source=recurring`; `subscriptions` przedłużona o cykl
(`current_period_start` = poprzedni `current_period_end`); faktura nowa.

**Wariant błędu — wygaśnięcie aliasu**: w Panelu tpay wyrejestruj alias
(lub wyślij notyfikację testową `ALIAS_EXPIRED` narzędziem panelu):
**Metody płatności** pokazują alias zawieszony; Owner dostaje powiadomienie
email „dodaj kartę lub ponów BLIK" (logi); kolejny przebieg schedulera bez
aktywnej metody → **dunning** (S11).

### S10. Odnowienie zapisaną kartą (token) (AC9)

**Przygotowanie**: tenant z aktywną subskrypcją i kartą domyślną (po S2);
`--reset` + restart.

1. Skróć `next_charge_at` (SQL §4.3) → `docker compose exec backend python
   scripts/run_billing_scheduler.py`.
2. Sandbox: obciążenie tokenem → `paid`.

**Oczekiwane**: jak S9 (przedłużenie, faktura, liczniki nowy okres).
**Wariant błędu**: `--scenario card_error_504` + restart → przebieg
schedulera → odmowa → **dunning** (próba 1; email „płatność nie powiodła się").

### S11. Dunning: 3 próby → downgrade do Freemium + grace (AC12)

**Przygotowanie**: subskrypcja płatna z metodą; cena wymuszająca porażkę
(np. `--scenario decline`); restart.

1. Uruchom `run_billing_scheduler.py` → porażka 1 (logi: „dunning (próba 1)",
   email do Ownera).
2. Skróć cooldown (SQL §4.3b) → przebieg → porażka 2; jw. → porażka 3.
3. Czwarty przebieg → **downgrade**: DB `status='past_due'`,
   `plan_id`=Freemium, `previous_plan_id`=poprzedni, `grace_until`≈+7 dni;
   email „subskrypcja obniżona".
4. **Grace**: limity planu dotychczasowego nadal obowiązują (Zużycie zasobów).
5. Po `grace_until` (SQL §4.3c przyspiesza) przebieg schedulera → egzekwja
   Freemium; **11. analiza** w miesiącu → **429 + banner „limit osiągnięty"
   z CTA upgrade** (GUI: uruchom analizę ponad limit).

### S12. Downgrade / anulowanie / reaktywacja (AC7, AC8)

**Przygotowanie**: tenant na Premium; `--reset` + restart.

1. Plany → zmiana na Basic (downgrade): GUI potwierdza „na koniec okresu";
   DB: `cancel_at_period_end=true`, `next_charge_at=NULL`;
   **asercja braku wywołań tpay** (logi backendu — żadnego żądania
   create/charge przy downgrade).
2. „Rezygnuj z zmiany" (reaktywacja): `cancel_at_period_end=false`,
   `next_charge_at` przywrócone; bez wywołań tpay.
3. Po `current_period_end` (SQL §4.3 przyspiesza) + przebieg schedulera:
   plan docelowy aktywny, email o zmianie.

### S13. Webhooki: idempotentność, chargeback, rozbieżność (AC11)

- **Duplikat**: w Panelu tpay → narzędzie testu powiadomień → wyślij tę samą
  notyfikację 2×. Weryfikacja: DB `webhook_events.processing_status` drugi
  raz = `duplicate`; subskrypcja/faktura bez zmian (brak podwójnych efektów).
- **Chargeback**: jeśli panel sandbox udostępnia chargeback na transakcji —
  wykonaj na opłaconej z S1. Weryfikacja: `payment_transactions.status =
  'charged_back'` + flaga ręcznej weryfikacji; **bez automatycznego
  downgrade'u** subskrypcji.
- **Odporność**: `GET /api/v1/billing/webhooks/health` (admin) — liczniki
  processed/duplicate rosną, brak serii błędów.

### S14. Limity, progi 80/90/100, rate limiting (AC13) — opcjonalnie

- Limity: przy Freemium po grace (S11) — 11. analiza → 429 + CTA.
- Progi: podnieś licznik SQL-em (§4.4: `value=8` przy limicie 10) → wywołaj
  zadanie progowe:
  ```bash
  docker compose exec backend celery -A app.workers.celery_app call \
    app.workers.tasks.check_thresholds.check_usage_thresholds
  ```
  → dzwonek in-app + email (logi).
- Rate limit: 101 żądanie/min z jednego konta → 429 z nagłówkami
  `X-RateLimit-*` (np. pętla `curl`).

## 4. Weryfikacje SQL / przyspieszanie czasu

Wykonanie: `docker compose exec postgres psql -U <user> -d <db> -c "..."`.

```sql
-- 4.1 Stan billingowy tenanta
SELECT s.status, s.cancel_at_period_end, s.current_period_end, s.next_charge_at,
       s.dunning_attempt, s.dunning_next_retry_at, s.grace_until, sp.name AS plan
FROM subscriptions s JOIN subscription_plans sp ON sp.id = s.plan_id
WHERE s.tenant_id = (SELECT id FROM tenants WHERE slug = '<slug>');

-- 4.2 Transakcje + webhooki + faktury
SELECT hidden_description, status, amount, paid_amount, test_mode,
       metadata->>'source' AS source, created_at FROM payment_transactions ORDER BY created_at DESC LIMIT 10;
SELECT event_uid, type, processing_status, error_message FROM webhook_events ORDER BY created_at DESC LIMIT 10;
SELECT invoice_number, status, issued_at FROM invoices ORDER BY issued_at DESC LIMIT 5;

-- 4.3 Przyspieszanie czasu (uwaga: tylko środowisko testowe!)
UPDATE subscriptions SET next_charge_at = now() - interval '1 hour'      -- wymagalność odnowienia
WHERE tenant_id = (SELECT id FROM tenants WHERE slug = '<slug>');
UPDATE subscriptions SET dunning_next_retry_at = now() - interval '1 hour'  -- (b) skróć cooldown dunningu
WHERE dunning_next_retry_at IS NOT NULL;
UPDATE subscriptions SET current_period_end = now() - interval '1 hour',  -- (c) wykonaj downgrade / grace
    grace_until = now() - interval '1 hour'
WHERE tenant_id = (SELECT id FROM tenants WHERE slug = '<slug>');

-- 4.4 Licznik analiz na 80% limitu Freemium (próg powiadomień)
INSERT INTO usage_counters (id, tenant_id, counter_type, value, limit_value, period_start, period_end)
VALUES (gen_random_uuid(), (SELECT id FROM tenants WHERE slug='<slug>'), 'analyses', 8, 10,
        date_trunc('month', now()), date_trunc('month', now()) + interval '1 month')
ON CONFLICT DO NOTHING;
```

## 5. Czyszczenie stanu między scenariuszami

- Ceny: `python scripts/set_sandbox_prices.py --reset` + restart.
- Tenant testowy: ustaw na Freemium (`UPDATE subscriptions s SET plan_id =
  (SELECT id FROM subscription_plans WHERE name='freemium'), status='active',
  cancel_at_period_end=false, next_charge_at=NULL, dunning_attempt=0,
  dunning_next_retry_at=NULL, grace_until=NULL, previous_plan_id=NULL WHERE
  s.tenant_id=...`; `UPDATE tenants SET plan='freemium' WHERE ...`) lub
  użyj `backend/scripts/reset_demo.py`.
- Ewentualne nowy tenant = czysty Freemium (najprostszy reset).

## 6. Kryteria zaliczenia (całość)

1. Każdy scenariusz S1–S13 (S14 opcjonalny) zakończony oczekiwanym wynikiem
   — w szczególności **strony błędów** (S4/S5/S6/S7) pokazują komunikat +
   ponowienie, tenant **zostaje na planie wyjściowym**.
2. `webhook_events` bez statusów `error` (poza celowo wywołanymi); health
   webhooków bez alertu.
3. Każda opłacona transakcja ma fakturę; `test_mode` = true wszędzie.
4. Po sesji: ceny zresetowane, tenant testowy na Freemium.
