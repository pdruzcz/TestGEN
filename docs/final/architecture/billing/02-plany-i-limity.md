# Plany subskrypcji i limity

> Dokumentacja P2, Epic 7 — model 3-planowy (CR#2, 2026-08-28).
> Implementacja: `backend/app/seed/seed_plans.py`, `backend/app/core/config_billing.py`.

## 1. Model 3-planowy

| Plan | Cena miesięczna | Pozycja |
|---|---|---|
| **Freemium** | 0,00 PLN | start — każdy nowy tenant |
| **Basic** | 30,00 PLN (`BILLING_BASIC_MONTHLY_PRICE`) | rozszerzenie analiz |
| **Premium** | 50,00 PLN (`BILLING_PREMIUM_MONTHLY_PRICE`) | pełen dostęp + priorytetowe wsparcie |

Zasady modelu (decyzje CR#2 z 2026-08-28):

- Jedyny cykl: **miesięczny** — brak pól rocznych, brak wersji trial.
- Nowy tenant startuje na Freemium (subskrypcja tworzona automatycznie —
  `create_freemium_subscription`).
- Dunning (niepłatność odnowienia) **zawsze** kończy się downgrade do
  Freemium — po 7 dniach grace (szczegóły: [05 — Tokeny i odnowienia](05-tokeny-i-odnowienia.md)).
- Ceny i URL-e regulaminu/polityki prywatności pochodzą z env — wymiana
  cen = zmiana env + restart (re-seed), bez deployu kodu.

## 2. Macierz limitów

`PLAN_FEATURES` w `seed_plans.py`; `None` = bez limitu:

| Limit | Freemium | Basic | Premium |
|---|---|---|---|
| Analizy / miesiąc | 10 | 50 | ∞ |
| Wygenerowane test case'y / miesiąc | 50 | 250 | ∞ |
| Storage | 0,5 GB | 5 GB | 10 GB |
| Plików na analizę | 5 | 25 | 50 |
| Żądania API / min (rate limit) | 100 | 100 | 1000 |
| Projekty | ∞ | ∞ | ∞ |
| Priorytetowe wsparcie | — | — | ✓ |

Liczniki (`CounterType` w `backend/app/models/usage.py`): `analyses`,
`test_cases`, `storage_bytes`, `files_per_analysis`. Egzekwowanie:
[07 — Limity i zużycie](07-limity-i-zuzycie.md).

## 3. Progi modułów analizy (feature gating)

Macierz `GATED_MODULES` — minimalny plan odblokowujący moduł:

| Moduł | Minimalny plan |
|---|---|
| Analiza kodu (`code_analysis`) | Freemium |
| Generowanie testów (`test_generation`) | Freemium |
| Analiza dokumentacji (`documentation`) | Basic |
| Analiza UML (`uml`) | Basic |
| Analiza GUI (`gui`) | Basic |
| Testy integracyjne (`integration_tests`) | Basic |
| Generator CI/CD (`ci_cd`) | Basic |
| Analiza bezpieczeństwa (`security`) | Premium |
| Rekomendacje bezpieczeństwa (`security_recommendations`) | Premium |
| Spójność kod↔dokumentacja (`code_doc_consistency`) | Premium |
| Luki funkcjonalne (`functional_gaps`) | Premium |

Zasada FR71: moduły poza planem są **widoczne-zablokowane** w UI (kłódka +
komunikat, który plan odblokowuje), a backend odpowiada **402** —
szczegóły: [08 — Powiadomienia i gating](08-powiadomienia-i-gating.md).

## 4. Seed planów

`seed_plans.py::seed_subscription_plans` uruchamiany w startup hooku:

1. Upsert 3 planów — brakujące tworzy, istniejące aktualizuje ceną z env
   (idempotentny; `features` i pola opisowe odświeżane przy każdym starcie).
2. Zasilenie cache limitów QuotaService (`set_plan_limits_cache`) — jedno
   źródło prawdy: baza, nie kod.
3. Zasilenie progów rate limitu (`set_rate_limits_cache`) — fallback
   awaryjny w configu obejmuje scenariusz pustego cache.

Struktura rekordu `subscription_plans` (globalna tabela referencyjna,
bez RLS): `name` (unikalny enum), `display_name`, `price_monthly`,
`currency`, `features` (JSONB — macierz limitów + `gated_modules`),
`is_active`, `sort_order`.

## 5. Migracja legacy (043)

Migracja `043_migrate_plan_type_to_three_tiers.py` przeprowadziła stare
wartości enuma `tenant.plan`: `basic` (dawny darmowy) → `freemium`,
`professional` → `premium`. Enum `plan_type_v3` jest źródłem dla hierarchii
planów (`PLAN_HIERARCHY` w `subscription_service.py`: freemium < basic
< premium) używanej przy klasyfikacji zmian planu na upgrade/downgrade.
