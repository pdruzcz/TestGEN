# Architektura modułu billingowego — przegląd

> Dokumentacja P2, Epic 7 — moduł billingowy TestGEN.
> Wersja odpowiada implementacji w `backend/app/services/billing/`.

## 1. Cel modułu

Moduł billingowy obsługuje monetyzację platformy: plany subskrypcji,
płatności przez tpay, faktury VAT, egzekwowanie limitów per plan oraz
kontrolę dostępu do modułów analizy (feature gating).

Główne funkcje:

- **FR54** — wybór planu subskrypcji (Freemium/Basic/Premium)
- **FR55** — zmiana planu w dowolnym momencie (proration, zaplanowane downgrade)
- **FR56** — płatności tpay: BLIK, karta, przelew (change request 2026-08-28 —
  jedyny provider, zastąpił Stripe + Przelewy24)
- **FR57** — automatyczne faktury VAT po każdej płatności
- **FR58** — egzekwowanie limitów per plan (analizy, test case'y, storage, pliki)
- **FR59** — powiadomienia o zbliżaniu się do limitów (80/90/100%)
- **FR52** — dashboard zużycia zasobów (liczniki, prognoza, historia)
- **FR71** — freemium feature gating — moduły analizy widoczne-zablokowane

## 2. Diagram przepływów

```
   Owner (Angular /billing/*)                tpay Open API
        │                                       │
        │ POST /billing/checkout                │
        ▼                                       │
  ┌──────────────────┐   POST /transactions    │
  │ PaymentTransaction│ ─────────────────────► │ Panel Transakcyjny
  │ (pending,         │                          │ (BLIK / karta / PBL)
  │  hidden_descr =   │ ◄─────────────────────  │
  │  order_id UUID)   │   transaction_payment_url
  └────────┬─────────┘                          │
           │ redirect płatnika                  │ notyfikacje (JWS)
           ▼                                    ▼
  ┌──────────────────┐                 ┌────────────────────┐
  │ /checkout/       │                 │ POST /billing/     │
  │  success|error   │                 │  webhooks/tpay     │
  │ (polling statusu)│                 │  (publiczny)       │
  └──────────────────┘                 └─────────┬──────────┘
                                                 │ klasyfikacja
                          ┌──────────────────────┼──────────────────┐
                          ▼                      ▼                  ▼
                   transakcja (form)      alias BLIK (form)   tokenizacja (JSON)
                   mark_paid              PaymentToken        PaymentToken
                          │                      │                  │
                          ▼                      │                  │
                   ┌────────────┐                │                  │
                   │ InvoiceSvc │ faktura VAT    │                  │
                   │ FV/…/0001  │ ── PDF ──► MinIO testgen-invoices
                   └────────────┘                │                  │
                                                 ▼                  ▼
                          Celery beat 03:30 — SubscriptionScheduler
                          (odnowienia z tokena, dunning, downgrade,
                           wygasły grace) → zawsze Freemium + 7 dni

  Każde żądanie (BE): QuotaService.check_quota → 402/429 lub inkrement
  FeatureGatingService.enforce_feature → 402 przy module poza planem
```

## 3. Moduły i ich odpowiedzialności

| Moduł | Plik | Rola |
|---|---|---|
| Subscription service | `services/billing/subscription_service.py` | Subskrypcje, zmiany planu, proration, tokeny, dunning |
| Quota service | `services/billing/quota_service.py` | Liczniki zużycia, limity, dashboard, prognoza |
| Invoice service | `services/billing/invoice_service.py` | Faktury VAT: numeracja, PDF, wysyłka, dane fakturowe |
| Webhook processor | `services/billing/webhook_processor.py` | Klasyfikacja i przetwarzanie notyfikacji tpay |
| Webhook metrics | `services/billing/webhook_metrics.py` | Liczniki Prometheus + snapshot health |
| Subscription scheduler | `services/billing/subscription_scheduler.py` | Zadania okresowe: odnowienia, dunning, downgrade |
| Feature gating | `services/billing/feature_gating.py` | Progi modułów per plan, zależność `require_feature` |
| Provider tpay | `services/billing/providers/tpay/` | Klient Open API: `auth.py`, `client.py`, `transactions.py`, `tokens.py`, `webhooks.py` |
| Notification service | `services/notification_service.py` | Powiadomienia o progach 80/90/100% (in-app + email) |
| Rate limit | `middleware/rate_limit.py` | Limit żądań/min per plan (100/100/1000) |
| Router API | `api/routes/billing.py` | 23 endpointy `/api/v1/billing/*` |
| Router webhooków | `api/routes/webhooks_tpay.py` | `POST /webhooks/tpay` (publiczny) + `GET /webhooks/health` (admin) |
| Seed planów | `seed/seed_plans.py` | Idempotentny upsert planów w startup hooku |
| FE billing | `frontend/src/app/features/billing/` | Portal: plans, checkout, payment-methods, subscription, transactions, invoices, usage |

## 4. Zadania okresowe (Celery beat)

`backend/app/workers/celery_app.py`:

| Zadanie | Harmonogram | Rola |
|---|---|---|
| `billing-usage-snapshot-daily` | 00:00 | Snapshot liczników do `usage_history` (zamyka dzień przed zmianą okresu) |
| `billing-subscription-renewals-daily` | 03:30 | Odnowienia cykliczne z tokenów, dunning, wygasły grace, zaplanowane downgrade |
| `billing-check-thresholds-hourly` | co godzinę | Progi zużycia 80/90/100% → powiadomienia (dedup per okres) |

Kolejność 00:00 → 03:30 jest celowa: snapshot dnia zamyka się przed
zmianą okresu rozliczeniowego.

## 5. Konfiguracja

Konfiguracja w `backend/app/core/config_billing.py` (env, bez deployu kodu):

- Ceny: `BILLING_BASIC_MONTHLY_PRICE` (30,00 PLN), `BILLING_PREMIUM_MONTHLY_PRICE`
  (50,00 PLN), `BILLING_CURRENCY` — Freemium zawsze 0.
- Dokumenty prawne: `BILLING_TERMS_URL`, `BILLING_PRIVACY_POLICY_URL`
  (regulamin i polityka prywatności osadzane na stronach zakupu — tpay tego
  wymaga; linki z configu, nigdy hardcode).
- tpay: `TPAY_ENV` (sandbox/production), `TPAY_CLIENT_ID`,
  `TPAY_CLIENT_SECRET`, `TPAY_SECURITY_CODE`, `TPAY_MERCHANT_ID`,
  URL-e powrotów i grupy płatności (szczegóły: [03 — Integracja tpay](03-integracja-tpay.md)).
- Faktury: dane sprzedawcy `INVOICE_SELLER_*` — snapshot do faktury
  w chwili wystawienia (szczegóły: [09 — Faktury VAT](09-faktury-vat.md)).

Sekrety tpay wyłącznie z env/secrets — nigdy w kodzie ani repo.

## 6. Zasady projektowe

- **Jedno źródło prawdy limitów** — macierz limitów mieszka w
  `subscription_plans.features` (JSONB, seed z `seed_plans.py`); cache
  QuotaService i progi rate limitu zasilane są z bazy przy starcie.
- **Dunning zawsze kończy się Freemium** — nie ma blokady konta za niepłatność;
  tenant traci plan płatny po 7 dniach grace, dane pozostają.
- **Operacje lokalne vs tpay** — anulowanie/reaktywacja subskrypcji i
  downgrade są operacjami lokalnymi (bez wywołań API tpay); obciążenia
  (checkout, odnowienie) zawsze przez tpay.
- **Idempotencja** — webhooki po `event_uid`, faktury po `payment_id`,
  plany przez upsert w seedzie.
- **RLS** — tabele tenanta (`subscriptions`, `usage_counters`, `invoices`,
  `payment_transactions`, `payment_tokens`, `plan_change_history`,
  `usage_history`, `notifications`) mają polityki `tenant_isolation` +
  `admin_bypass`; `subscription_plans` to globalna dane referencyjne (bez RLS).

## 7. Powiązane dokumenty

- [02 — Plany i limity](02-plany-i-limity.md)
- [03 — Integracja tpay](03-integracja-tpay.md)
- [04 — Webhooki](04-webhooki.md)
- [10 — Modele danych](10-modele-danych.md)
