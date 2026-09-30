# Macierz scenariuszy płatności — Story 7.12

Zautomatyzowana macierz testowa modułu billing (tpay — jedyny provider).
Źródło danych sterujących: **§2.1 planu integracji tpay**
(`_bmad-output/planning-artifacts/plan-integracji-tpay.md`) — karty testowe,
kwoty sterujące 3DS/błędami, kody BLIK, zakresy PAYID. Stałe pomocnicze w
`tests/fixtures/tpay_fixtures.py` — **to NIE są ceny planów** (ceny z env,
§3.2a; domyślne testowe 30/50 PLN).

## Warstwy

| Warstwa | Kto biega | Kiedy |
|---|---|---|
| Scenariuszowe z mockami tpay (`tests/scenarios/`) | każdy CI (`backend-tests` + dedykowany `billing-tests`) | zawsze |
| Integracyjne z prawdziwym sandboxem (`tests/integration/test_tpay_sandbox.py`, markery `billing` + `tpay_sandbox`) | job `billing-tests` | tylko gdy sekrety `TPAY_*` w CI; bez → skip z reason |
| Ręczna weryfikacja na środowisku testowym (GUI + skrypty cen/schedulera) | człowiek wg [runbooka sandboxa](../../../docs/final/troubleshooting/tpay-sandbox-runbook.md) | po zgłoszeniu środowiska do sandboxa tpay |

Sandbox: `TPAY_SANDBOX_E2E=1` + `TPAY_ENV=sandbox` + sekrety
(`TPAY_CLIENT_ID`/`TPAY_CLIENT_SECRET`/`TPAY_SECURITY_CODE`/`TPAY_MERCHANT_ID`).
W sandboxie **maile do płatników są zablokowane** — wszystkie asercje mailowe
na mockach (ryzyko §4.4). Asercje obowiązkowe każdego scenariuszu sandbox:
webhook ma `test_mode = 1`, odpowiedź webhooka = `TRUE`.

## Macierz scenariuszy

| # | AC | Scenariusz | Dane sterujące (§2.1) | Oczekiwany wynik | Plik |
|---|----|-----------|------------------------|------------------|------|
| 1 | AC1 | Zakup planu płatnego BLIK | kod `777xxx` | `paid` → aktywacja, faktura (7.6), email (mock), nowy okres, `test_mode=1` | `test_scenario_purchase_blik.py` |
| 2 | AC2 | Zakup kartą (sukces) + `save=1` | karta `2223 0002 8000 0016` / `4056 2178 4359 7258`, CVC 3 cyfry, przyszła data | `paid` + `card_token` w webhooku → `PaymentToken` zapisany (7.2 AC1) | `test_scenario_purchase_card.py` |
| 3 | AC3 | Zakup przelewem (PBL) | lista banków sandbox (Panel) | `tr_status=true` aktywuje plan; status na stronie powrotu | `test_scenario_purchase_card.py` |
| 4 | AC4 | 3DS sterowany groszami | `*.x1` frictionless, `*.x3` sukces, `*.x5` błąd 3DS, `*.x6` decline, inne → challenge | `x1`/`x3` → aktywacja; `x5`/`x6` → porażka, tenant na planie wyjściowym; challenge po potwierdzeniu → aktywacja | `test_scenario_3ds_errors.py` |
| 5 | AC5 | Błędy płatności (kwoty) | karta/wallety: `500/501/503/504`; BLIK: `144` (płatnik), `168` (wystawca), `120` (brak środków), `312` (timeout), `96` (limit), `216` (bezpieczeństwo) | porażka bez aktywacji; błąd widoczny na stronie powrotu; ponowienie checkoutu możliwe | `test_scenario_3ds_errors.py` |
| 6 | AC6 | Upgrade z proration (7.5) | Basic w połowie okresu → Premium; Freemium→płatny = pełna cena | kwota prorated = preview↔charge; po `paid` plan natychmiast Premium, liczniki zachowane, `plan_change_history` z `proration_details` | `test_scenario_plan_changes.py` |
| 7 | AC7 | Downgrade + anulowanie | Premium→Basic, Premium→Freemium, Basic→Freemium | `cancel_at_period_end=true`, `next_charge_at` stop, **brak wywołań tpay**; scheduler egzekwuje plan docelowy po `current_period_end` | `test_scenario_plan_changes.py` |
| 8 | AC8 | Reaktywacja anulowanej | — | `cancel_at_period_end=false`, `next_charge_at` przywrócone, plan kontynuowany bez tpay | `test_scenario_plan_changes.py` |
| 9 | AC9 | Odnowienie kartą (token) | `pay.cardPaymentData.token` | transakcja merchant-initialized; webhook `paid` przedłuża okres (`next_charge_at += cykl`), faktura, liczniki na nowy okres | `test_scenario_recurring.py` |
| 10 | AC10 | Odnowienie BLIK PAYID | alias z kwoty `x.08–x.15`; `495.00`+`mock` → refuseNoPayId | odnowienie bez udziału użytkownika (`blikPaymentData.type=2`); `ALIAS_EXPIRED`/`ALIAS_UNREGISTER` → token suspended + powiadomienie Ownera; refuseNoPayId → 422 z sugestią karty | `test_scenario_recurring.py` |
| 11 | AC11 | Webhook: idempotentność, chargeback | ten sam `event_uid` ×2; `tr_status=chargeback`; `tr_paid != tr_amount` | duplikat → `TRUE` + audyt DUPLICATE (bez podwójnej aktywacji); chargeback → `charged_back` + flaga ręcznej weryfikacji, bez automatycznego downgrade; rozbieżność kwot → flaga + alert | `test_scenario_webhooks.py` |
| 12 | AC12 | Dunning (3 próby → downgrade) | D+1/D+3/D+5 (mock czasu `run(now=…)`) | po 3 ponowieniach: `past_due` → **downgrade do Freemium** + 7 dni grace (limity planu dotychczasowego); po grace limity Freemium (429 `limit_reached`); emaile: 3× próba + 1× downgrade | `test_scenario_webhooks.py` |
| 13 | AC13 | Limity + progi powiadomień | liczniki 0/50/80/90/100% (limit analiz Freemium = 10 z `features` 7.1) | ponad limit → 429 `limit_reached` z `upgrade_url` (FE upgrade CTA); progi 80/90/100 → in-app + email (mock) z deduplikacją | `test_scenario_limits.py` |
| 14 | AC13 | Rate limiting | próg 100 żądań/min (Freemium, Redis) | 101. żądanie/min → 429 + `X-RateLimit-Limit/Remaining/Reset` + `Retry-After` | `test_scenario_limits.py` |

## Notatki implementacyjne (odchylenia od literału AC)

- **AC3 (PBL)**: notyfikacja transakcyjna tpay nie niesie grupy/kanału płatności
  (ograniczenie u źródła — patrz Dev Agent Record 7.6); metoda „przelew" nie
  jest odrębnym polem API. Scenariusz asercjuje kontrakt transakcyjny + status
  strony powrotu.
- **AC7 („anuluje subskrypcję 7.7")**: portal bilingowy 7.7 oczekuje na
  implementację; scenariusz pokrywa semantykę backendową (downgrade =
  `cancel_at_period_end` + stop obciążeń, bez wywołań tpay), na której 7.7
  będzie operował.
- **AC12 (in-app przy każdej próbie dunningu)**: dunning wysyła wyłącznie
  emaile (3× próba + 1× downgrade); powiadomienia in-app (dzwonek) obejmują
  progi limitów (7.11), nie dunning — poza zakresem 7.1–7.8.
- **Mock czasu**: `SubscriptionScheduler.run(now=...)` przyjmuje chwilę
  przebiegu (seam testowy 7.2) — freezegun niepotrzebny (bez nowej zależności).
  Wygaśnięcie grace symulowane na danych (`grace_until` w przeszłości), bo
  `enforce_grace_expiry` rewaliduje progi zegarem wall-clock.
- **Porażka zakupu (nie-recurring)**: `tr_status=false` → status
  `charged_back` (ścieżka „ręczna weryfikacja" 7.4 AC5/AC6) — scenariusz
  dokumentuje faktyczne zachowanie.

## Uruchomienie

```bash
cd backend
python -m pytest tests/scenarios/ -v            # z mockami (każdy CI)

# Integracyjne z prawdziwym sandboxem (opt-in, sekrety):
TPAY_SANDBOX_E2E=1 TPAY_ENV=sandbox \
TPAY_CLIENT_ID=... TPAY_CLIENT_SECRET=... TPAY_SECURITY_CODE=... TPAY_MERCHANT_ID=... \
python -m pytest tests/integration/test_tpay_sandbox.py -m "billing or tpay_sandbox"
```
