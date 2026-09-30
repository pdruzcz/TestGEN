# Zmiany planu i proration

> Dokumentacja P2, Epic 7 — Story 7.5 (+ interakcje z 7.7).
> Implementacja: `backend/app/services/billing/subscription_service.py`
> (`calculate_proration`, `change_plan`, `PlanChangeHistory`).

## 1. Klasyfikacja zmiany

Hierarchia planów: `freemium < basic < premium` (`PLAN_HIERARCHY`).

| Zmiana | Tryb | Rozliczenie |
|---|---|---|
| Upgrade (płatny → wyższy płatny) | płatność natychmiast przez tpay | proration — różnica proporcjonalna do pozostałych dni okresu |
| Z Freemium → Basic/Premium | płatność natychmiast | pełna cena nowego planu (brak komponentu prorated) |
| Downgrade | **lokalnie**, efektywny na koniec okresu | 0,00 — rozliczenie na koniec okresu, bez zwrotów |
| Downgrade → Freemium (anulowanie) | lokalnie (Story 7.7 §3.5) | j.w. — dostęp do końca okresu |

Krawędź: upgrade w **ostatni dzień okresu** daje kwotę 0,00
(wynik ujemny przycięty do zera) — zmiana bez obciążenia, natychmiastowa.

## 2. Formuła proration

Czysta funkcja `calculate_proration` (Decimal, ROUND_HALF_UP, 2 miejsca):

```
płatny → płatny (upgrade):
    kwota = ((cena_nowa / dni_okresu) × pozostałe_dni)
          − ((cena_stara / dni_okresu) × pozostałe_dni)
    kwota  = max(kwota, 0,00)

z Freemium:      kwota = pełna cena nowego planu
downgrade:       kwota = 0,00
```

Wynik zwracany jako słownik audytowy (`amount`, `period_days`,
`remaining_days`, ceny obu planów) — trafia do `proration_details`
rekordu `PlanChangeHistory`. Podgląd bez skutków:
`GET /billing/subscription/proration?plan=…` (Owner; kwota liczona
lokalnie — D2, bez API tpay; ten sam plan → 400).

## 3. Przepływ upgrade

`POST /billing/subscription/change` (Owner) → `_start_upgrade`:

1. Blokada subskrypcji (`FOR UPDATE` — `_get_subscription_locked`).
2. `calculate_proration`; kwota > 0 → checkout tpay jak w 7.4 z
   `meta.plan_change_id`; rekord `PlanChangeHistory` (`pending_payment`).
3. Webhook `paid` → `finalize_plan_upgrade`: natychmiastowa zmiana planu,
   przesunięcie okresu start na teraz, rekord `completed`.
4. Webhook płatności nieudanej / porażka → `cancel_failed_plan_change`:
   plan bez zmian, rekord `failed`, email wyjaśniający.
5. Kwota ≤ 0,00 (np. ostatni dnia okresu) → `_apply_free_upgrade`:
   zmiana natychmiast, bez wywołań tpay.

Ten sam plan → 400; downgrade w trakcie dunningu → 409.

## 4. Przepływ downgrade (zaplanowany)

`_schedule_downgrade`: operacja czysto lokalna — `cancel_at_period_end`,
`previous_plan_id`, rekord `PlanChangeHistory` (`scheduled`), zapamiętane
`next_charge_at`. Nowy plan obowiązuje od końca bieżącego okresu:
`SubscriptionScheduler` (03:30) wykonuje `execute_scheduled_downgrade`
po upływie okresu.

Rezygnacja z zaplanowanego downgrade:
`POST /billing/subscription/change/cancel-pending` (Owner) — rekord
`canceled`, zdjęcie `cancel_at_period_end`, przywrócone `next_charge_at`.
Brak oczekującej zmiany → 404.

## 5. Historia zmian

`GET /billing/subscription/history` (Owner) — rekordy `PlanChangeHistory`
(migracja 047): typ zmiany (upgrade/downgrade), plan z → plan na, status
(`scheduled` / `pending_payment` / `completed` / `failed` / `canceled`),
`proration_details`, kwota. Najnowsze pierwsze — audyt pełnego cyklu życia
subskrypcji.

## 6. Interakcje z anulowaniem subskrypcji (Story 7.7)

- `cancel_subscription` przy **zaplanowanym downgrade** = operacja
  idempotentna — rekord zmiany pozostaje nietknięty, na koniec okresu
  obowiązuje plan niższy (downgrade wykonuje się zamiast powrotu do
  Freemium).
- `reactivate_subscription` przy oczekującej zmianie planu → **409**
  (najpierw rozstrzygnij zmianę: `cancel-pending` albo zaczekaj).
