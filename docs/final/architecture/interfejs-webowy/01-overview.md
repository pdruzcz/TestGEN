# Architektura frontendu — przegląd

> Dokumentacja P2, Epic 6 — interfejs webowy TestGEN.
> Wersja odpowiada implementacji w `frontend/src/app/`.

## 1. Cel

Frontend dostarcza kompletny interfejs platformy: zarządzanie projektami
i uploadem, uruchamianie i konfigurację analiz, przeglądanie wyników,
zarządzanie test case'ami, raporty i eksporty (FR43–FR46) — w standardzie
dostępności **WCAG 2.1 AA** na każdym ekranie.

## 2. Stack technologiczny

| Warstwa | Technologia |
|---|---|
| Framework | Angular 21, **komponenty standalone** (bez NgModules) |
| UI kit | Angular Material (MD3) |
| Stan | **Signals** + `rxjs-interop` (`toSignal`/`takeUntilDestroyed`) |
| Style | SCSS, tokeny w `shared/styles/` |
| Testy jednostkowe | Vitest przez `ng test` (builder `@angular/build:unit-test`) — ze ścisłą type-checką speców |
| Testy E2E | Playwright + axe-core (`frontend/e2e/`) |
| Powłoka natywna | Flutter 3.38 WebView (`mobile/`) — patrz [07 — Shell Flutter](07-shell-flutter.md) |
| Język UI | Polski (pełny interfejs, łącznie z komunikatami błędów i paginacją Material) |

Konwencje kodu: serwisy wstrzykiwane przez `inject()`, dane z HTTP przez
signals, subskrypcje wiązane z cyklem życia komponentu
(`takeUntilDestroyed`), wszystkie stringi UI po polsku.

## 3. Routing

`frontend/src/app/app.routes.ts` — lazy loading komponentów
(`loadComponent`/`loadChildren`), przekierowanie główne → `/dashboard`,
wildcard `**` → 404. Grupy tras:

| Grupa | Przykłady tras | Uwagi |
|---|---|---|
| Autoryzacja | `/login`, `/register`, `/verify-email`, `/set-password`, `/reset-password`, `/mfa-verify`, `/select-tenant` | publiczne (guard odwrotny) |
| Dashboard | `/dashboard` | strona główna po zalogowaniu |
| Projekty | `/projects`, `/projects/:id/{files,preprocessing,documents,analysis,results,…}` | największa grupa — wszystkie moduły analiz jako dzieci projektu |
| Moduły analiz | `…/{requirements,glossary,inconsistencies,coverage-report,gap-analysis,compliance,code-errors,recommendations,comparison,integrations,traceability,security,healing,gui,gherkin}` | E2–E5 + domknięcia |
| Generatory kodu | `…/codegen/{cypress,database,php,…}` | E1/E8 |
| Test case'y | `…/test-cases`, `…/test-cases/:testCaseId` | zarządzanie TC (6-5) |
| Raporty | `…/reports` | 6-6/6-7 |
| Ustawienia | `/settings/{profile,mfa,users}`, `/users/invite` | profil, MFA, użytkownicy |
| Billing | `/billing` (lazy — `BILLING_ROUTES`) | Epic 7 |
| Admin | `/admin`, `/admin/cve-pipeline` (lazy) | 6-15 |
| Błędy | `/403`, 404 (wildcard) | forbidden/not-found |

Ochrona tras: `auth.guard.ts` (zalogowany) i `role.guard.ts` (rola —
np. `/admin` wymaga Admin, ustawienia użytkowników — Owner).

## 4. Komunikacja z backendem

- HTTP przez `HttpClient`; `auth.interceptor.ts` dokleja token/nagłówki
  uwierzytelnienia i obsługuje 401; `snake-case.interceptor.ts` normalizuje
  konwencję nazewniczą pól (backend snake_case ↔ frontend camelCase) —
  źródło prawdy o kształcie pól w AOT (błędy widać dopiero w
  `ng build --configuration=production`).
- Konfiguracja runtime: `core/services/config.service.ts`.
- Błędy HTTP mapowane na polskie komunikaty na ekranach.

## 5. Dostępność jako wymiar poprzeczny

WCAG 2.1 AA obowiązuje na **każdym** ekranie — fundamenty (semantyka,
fokus, skip-link), motywy (wysoki kontrast, redukcja animacji), ARIA/czytniki
ekranu oraz audyt axe-core w testach. Rozdziały
[04 — Fundamenty](04-fundamenty-dostepnosci.md),
[05 — Motywy](05-motywy-dostepnosci.md),
[06 — ARIA](06-aria-screen-reader.md),
[08 — Testy](08-testy.md).

## 6. Powiązane dokumenty

- `docs/final/deployment-guide/getting-started.md` — uruchomienie frontendu lokalnie.
- `docs/final/user-guide/billing/` — ekrany `/billing/*`.
- Wzorce backendu: `docs/final/architecture/system.md`.
