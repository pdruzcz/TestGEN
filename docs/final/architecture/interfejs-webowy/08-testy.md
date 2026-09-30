# Strategia testowa frontendu

> Dokumentacja P2, Epic 6 — Story 6-13.
> Implementacja: specy `*.spec.ts` przy komponentach, `frontend/e2e/`,
> `frontend/playwright.config.ts`.

## 1. Poziomy testów

| Poziom | Narzędzie | Zakres |
|---|---|---|
| Jednostkowe/komponentowe | **Vitest przez `ng test`** (builder `@angular/build:unit-test`) | każdy komponent, serwis, guard, dyrektywa ma `*.spec.ts` |
| E2E | **Playwright** (`frontend/e2e/`) | przepływy przez UI na uruchomionym frontendzie |
| Dostępność | **axe-core** (`@axe-core/playwright`) | audyt WCAG na kluczowych trasach (w E2E) |
| AOT/typy | `ng build --configuration=production` | łapie błędy typów w szablonach niewidoczne dla testów |

Uruchomienie testów: `npm test` (= `ng test`). Uwaga: bezpośrednie
`npx vitest` omija inicjalizację TestBed i psuje wszystkie specy —
zawsze `ng test`. Builder wykonuje też ścisłą type-checkę speców, więc
zmiany interfejsów TS (nowe pola → opcjonalne `?`) wywalują testy,
zanim trafią do CI.

## 2. Testy komponentowe (Vitest)

- Setup TestBed per spec, mocki HTTP (`provideHttpClient` z interceptorami
  testowymi), signals testowane przez `signal()` + `fixture.detectChanges()`,
- a11y komponentowo: dedykowane specy dostępności przy dużych feature'ach
  (`admin.a11y.spec.ts`, `billing.a11y.spec.ts`) — struktura nagłówków,
  etykiety, role,
- guards/interceptory testowane na routingach i żądaniach HTTP.

## 3. E2E — Playwright

`frontend/e2e/`:

| Plik | Przepływ |
|---|---|
| `auth.spec.ts` | rejestracja, weryfikacja, logowanie, MFA, wybór tenanta |
| `dashboard.spec.ts` | strona główna, lista projektów |
| `upload.spec.ts` | upload drag & drop, walidacje, błędy |
| `analysis.spec.ts` | konfiguracja i uruchomienie analizy, wyniki |
| `report.spec.ts` | raporty dwupoziomowe, eksporty |
| `accessibility.spec.ts` | audyt axe-core (sekcja 4) |

Page Objecty w `e2e/pages/` (`auth.page`, `dashboard.page`, `upload.page`,
`analysis.page`, `report.page`), wspólne fixtury w `e2e/fixtures/`
(`test-fixtures.ts` — uwierzytelniona sesja, przygotowany projekt).

## 4. Audyt dostępności w CI (axe-core)

`accessibility.spec.ts` — konwencja ze Story 6-9 (`accessibility/
axe-runner.ts` i `shared/utils/axe-setup`):

- tagi: `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`,
- próg zaliczenia: **0 naruszeń o impact `critical` lub `serious`**,
- skan kluczowych tras (dashboard, projekt, wyniki, TC, raporty, billing,
  admin) w obu motywach dostępności (standardowy i wysoki kontrast).

## 5. Produkcja (AOT)

`ng build --configuration=production` jest obowiązkowym krokiem przed
mergem/CI: kompilacja AOT wyłapuje błędy typów w szablonach (nazwy pól
camelCase/snake_case po interceptorze, martwe `@if`, typy `$event`),
których `ng test` nie widzi. Regresje AOT łamały już deploy Dockera —
dlatego build produkcyjny biega przed publikacją obrazu.
