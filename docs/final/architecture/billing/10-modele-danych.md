# Modele danych modułu billingowego (ERD)

> Dokumentacja P2, Epic 7. Modele: `backend/app/models/` —
> `subscription_plan.py`, `subscription.py`, `payment.py`, `plan_change.py`,
> `invoice.py`, `invoice_data.py`, `usage.py`, `usage_history.py`,
> `notification.py`.

## 1. Diagram relacji

```
tenants ──1:1── subscriptions ──n:1── subscription_plans (global, bez RLS)
   │                │
   │                ├──1:n── plan_change_history (audyt zmian)
   │                └──1:1── payment_tokens (is_default → token odnowień)
   │
   ├──1:n── payment_transactions ──1:n── webhook_events (audyt, event_uid)
   │              │
   │              └──1:1── invoices (idempotencja po payment_id)
   │                            │
   ├──1:1── invoice_data (dane fakturowe → snapshot nabywcy)
   │
   ├──1:n── usage_counters (4 typy liczników, okno miesięczne)
   ├──1:n── usage_history (snapshot dzienny 00:00)
   └──1:n── notifications (progi 80/90/100%, RLS)
```

Wszystkie tabele tenanta mają polityki RLS `tenant_isolation` +
`admin_bypass` (wzorzec z migracji 041 — `current_setting('app.current_tenant')`).

## 2. Tabele

### subscription_plans (042 — globalna, bez RLS)

`name` (enum `freemium|basic|premium`, unikalny), `display_name`,
`price_monthly NUMERIC(10,2)`, `currency`, `features JSONB` (macierz
limitów + `gated_modules`), `is_active`, `sort_order`.

### subscriptions (042, 045, 047)

Dokładnie **jedna na tenanta** (`ix_subscriptions_tenant_id` unique):
`plan_id`, `status` (`active|past_due|canceled|incomplete`),
`current_period_start/end`, `next_charge_at` (indeks — scheduler),
`cancel_at_period_end`, `trial_end`, `payment_token_id` (metoda odnowień),
`dunning_attempt`, `dunning_next_retry_at` (045), `grace_until` (045),
`previous_plan_id` (047 — plan przed dunningiem).

### payment_transactions (044)

`provider` ("tpay"), `transaction_id` (ID u tpay), `title`,
`hidden_description` (order_id UUID — korelacja webhooka po `tr_crc`,
unikalny, indeks), `amount NUMERIC(10,2)`, `currency`,
`status` (`pending|paid|failed|…`), `paid_amount`, `test_mode`,
`meta JSONB` (plan, payer, `blik_alias_value`, `plan_change_id`).

### webhook_events (044, 046)

Audyt każdej notyfikacji, także odrzuconej: `event_uid` (unikalny —
idempotencja), `type` (transaction/alias/tokenization), `raw JSONB`,
`processing_status` (`processed|skipped|error|rejected_*`),
`error_message` (046).

### payment_tokens (045)

Metody płatności: `kind` (`card|blik`), `value_encrypted` (AES per-tenant),
`value_digest` (indeks wyszukiwania), `card_tail`, `card_brand`,
`expires_at`, `tpay_status` (`TpayTokenStatus`), `is_default`,
`registration_id` (unikalny — link do potwierdzenia rejestracji karty).

### plan_change_history (047)

Audyt zmian planu: typ (`upgrade|downgrade`), plan z/na, status
(`scheduled|pending_payment|completed|failed|canceled`),
`proration_details JSONB`, kwota.

### invoices + invoice_data (048)

Faktura: `invoice_number` (`FV/{rok}/{miesiąc}/{seq}`), `year`, `month`,
`sequential_number` (unikat razem z year/month), `issue_date`,
`sale_date`, snapshoty sprzedawcy i nabywcy (`seller_name/nip/address`,
`buyer_name/nip/address`), `items JSONB`, `subtotal_net`, `vat_rate`,
`vat_amount`, `total_gross`, `currency`, `payment_method`,
`payment_id` (idempotencja), `status`.

Dane fakturowe: 1:1 z tenantem — nazwa, NIP, adres.

### usage_counters (042)

Licznik per tenant i typ (`analyses|test_cases|storage_bytes|files_per_analysis`)
w oknie miesięcznym; inkrementy z endpointów i zadań.

### usage_history (049)

Snapshot dzienny (00:00): data, typ licznika, wartość — pod wykresy
i prognozy (≥7 dni danych).

### notifications (050)

Powiadomienia in-app: `user_id`, typ (próg zużycia), treść, `read_at`,
`dedup_key` (per tenant/okres/próg).

## 3. Rejestr migracji

| Migracja | Zakres | Story |
|---|---|---|
| 042 | `subscription_plans`, `subscriptions`, `usage_counters` + RLS | 7.1 |
| 043 | migracja danych do modelu 3-planowego (`plan_type_v3`) | 7.1 (CR#2) |
| 044 | `payment_transactions`, `webhook_events` | 7.4 |
| 045 | `payment_tokens`, pola dunningu subskrypcji | 7.2 |
| 046 | `webhook_events.error_message` | 7.3 |
| 047 | `plan_change_history` (renumber po kolizji z 7.5) | 7.5 |
| 048 | `invoices`, `invoice_data` | 7.6 |
| 049 | `usage_history` | 7.9 |
| 050 | `notifications` | 7.11 |

Konwencja migracji: idempotentny raw SQL, `DO $$ … EXCEPTION` na
dublowane enumy, advisory lock w `migrations/env.py` (kolizje revision
ID przy równoległych story — patrz `_ENUMS` w 042).
