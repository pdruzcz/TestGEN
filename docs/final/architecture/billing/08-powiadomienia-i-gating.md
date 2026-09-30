# Powiadomienia o limitach i feature gating

> Dokumentacja P2, Epic 7 — Stories 7.11, 7.13.
> Implementacja: `backend/app/services/notification_service.py`,
> `backend/app/services/billing/feature_gating.py`,
> `backend/app/api/routes/notifications.py`.

## 1. Powiadomienia o progach zużycia (Story 7.11)

Cykl godzinowy (`billing-check-thresholds-hourly`) →
`NotificationService.check_and_notify_thresholds()`:

1. Dla każdego aktywnego tenanta: pobierz zużycie (QuotaService) i Ownera.
2. Próg przekroczony (80 / 90 / 100% któregoś licznika) →
   `_create_notification`:
   - rekord `notifications` (RLS, migracja 050) — in-app,
   - email (szablon Jinja2 `render_limit_warning_body`) — gdy preferencje
     kanałów na to pozwalają,
   - **dedup per okres rozliczeniowy** — tenant dostaje każde ostrzeżenie
     progu (80/90/100%) maksymalnie raz w oknie; kolejne przebiegi
     godzinowe nie spamują.

Preferencje kanałów (in-app / email) trzyma profil użytkownika —
`_get_prefs` / `_prefs_enabled`. Formatowanie wartości per typ licznika
(`_format_value`): analizy i test case'y — liczby, storage — MB/GB.

### API i UI

| Element | Lokalizacja |
|---|---|
| `GET /api/v1/notifications` | lista powiadomień z paginacją |
| `GET /api/v1/notifications/unread-count` | licznik nieprzeczytanych |
| `POST /api/v1/notifications/{id}/read` | oznacz jako przeczytane |
| `POST /api/v1/notifications/read-all` | oznacz wszystkie |
| Dzwonek w navbarze | licznik nieprzeczytanych, lista, „oznacz wszystkie" |
| Preferencje w profilu | przełączniki kanałów (in-app / email) |

## 2. Feature gating modułów analizy (Story 7.13, FR71)

Zasada **widoczne-zablokowane**: moduł poza planem jest widoczny w UI
z kłódką i komunikatem, który plan go odblokowuje — użytkownik wie, co
zyskuje wyższym planem. Blokada nie jest ukryciem.

### Backend

`FeatureGatingService` (`feature_gating.py`):

- `evaluate(tenant, module)` → `(allowed, required_plan)` — próg z
  `gated_modules` macierzy planów (seed 7.1),
- `enforce_feature(tenant, module)` → rzut **402** z informacją o wymaganym
  planie,
- `require_feature(module)` — zależność FastAPI do wpięcia w router
  (używana na 20+ endpointach modułów analizy),
- `GET /api/v1/billing/features` — status wszystkich modułów dla planu
  tenanta (pod UI: odblokowane/zablokowane + wymagany plan).

### Frontend

`ModuleLocksService` ładuje status modułów i wystawia sygnał reaktywny:

- `locked-feature-tab` / `locked-module` — zakładka/panel z kłódką,
- banner 402 — globalna obsługa odpowiedzi 402 (komunikat + CTA do planów),
- **reaktywny unlock** — po zmianie planu statusy odświeżają się bez
  przeładowania strony.

Macierz progów: [02 — Plany i limity](02-plany-i-limity.md), sekcja 3.
