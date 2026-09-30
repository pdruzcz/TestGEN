# Limity i zużycie zasobów

> Dokumentacja P2, Epic 7 — Stories 7.8, 7.9.
> Implementacja: `backend/app/services/billing/quota_service.py`,
> `backend/app/api/routes/billing.py` (`/usage*`),
> `backend/app/workers/tasks/usage_snapshot.py`.

## 1. Liczniki i egzekwowanie

`QuotaService` operuje na tabeli `usage_counters` (RLS, migracja 042);
okno rozliczeniowe = miesiąc kalendarzowy okresu subskrypcji
(`_month_window` — od `current_period_start` do `current_period_end`):

| Operacja | Zachowanie |
|---|---|
| `check_quota(tenant, counter)` | `True`/`False` — Czy limit pozwala na +1? |
| `enforce_quota(tenant, counter)` | `check` + rzut 402/429 przy przekroczeniu (używane jako bramka w endpointach) |
| `increment_usage(tenant, counter, value)` | Inkrement w oknie; zapis wartości bezwzględnej dla `storage_bytes` |
| `check_storage_limit(tenant, bytes)` | Osobna ścieżka storage — suma bajtów plików vs limit planu |

Limity pochodzą z `subscription_plans.features` (cache zasilany seedem —
jedno źródło prawdy w DB; fallback env tylko przy pustym cache).
`None` = bez limitu. Wersje synchroniczne (`increment_usage_sync`,
`remaining_quota_sync`) służą procesom workera (sync engine).

Rate limit żądań API (100/100/1000 per min) egzekwuje osobny middleware
`app/middleware/rate_limit.py` — progi też z DB przez
`set_rate_limits_cache`.

## 2. Dashboard zużycia (Story 7.9)

`GET /billing/usage` — płaskie liczniki; `GET /billing/usage/dashboard` —
komplet pod UI (`DashboardData`):

- liczniki per typ z wartością, limitem, procentem zużycia,
- okno rozliczeniowe (start/koniec/dni pozostałe),
- prognoza wyczerpania limitu (`ForecastData`).

Frontend: `/billing/usage` — karty z paskami postępu
(`usage-card.component`), wykres historii po rozwinięciu karty
(`usage-chart.component` — natywne SVG, bez bibliotek wykresów).

## 3. Prognoza limitu

`calculate_forecast(tenant, counter)`:

- wymaga co najmniej 7 dni danych historycznych (krótszy okres → brak
  prognozy — brak podstaw statystycznych),
- dzienny przyrost = średnia z `usage_history` w bieżącym oknie,
- ekstrapolacja do końca okresu → flaga `exceeds_before_period_end`
  (limit zostanie wyczerpany przed końcem okresu rozliczeniowego).

Prognoza pokazywana na karcie licznika jako ostrzeżenie — pozwala
z wyprzedzeniem zmienić plan (upgrade natychmiastowy — Story 7.5).

## 4. Historia zużycia

Snapshot liczników codziennie o 00:00 (`billing-usage-snapshot-daily`,
`usage_snapshot.py`) do tabeli `usage_history` (RLS, migracja 049).
Snapshot zamyka dzień **przed** zmianą okresu (renewals 03:30) — wartość
dnia jest stabilna niezależnie od odnowień.

`GET /billing/usage/history?counter=analyses&days=30` — seria punktów
`UsageDataPoint` (data, wartość) pod wykres; `GET /billing/usage/history`
bez filtra zwraca wszystkie typy.
