# Struktura aplikacji Angular

> Dokumentacja P2, Epic 6. Katalog: `frontend/src/app/`.

## 1. Warstwy

```
frontend/src/app/
├── app.routes.ts          # routing główny (lazy loading)
├── core/                  # infrastruktura aplikacji (raz, globalnie)
│   ├── guards/            # auth.guard, role.guard
│   ├── interceptors/      # auth.interceptor, snake-case.interceptor
│   └── services/          # auth.service, config.service, module-locks.service
├── shared/                # elementy wielokrotnego użytku
│   ├── components/        # navbar, footer, file-upload, live-region, …
│   ├── directives/        # dostępność: focus-visible, keyboard-nav, …
│   ├── services/          # theme, upload, file-validation, live-announcer, …
│   ├── styles/            # tokeny SCSS + motywy dostępności
│   ├── i18n/              # polish-paginator-intl (paginacja Material po polsku)
│   ├── models/ constants/ utils/ validators/ interceptors/ base/
├── features/              # domeny funkcjonalne (lazy)
│   ├── dashboard/ projects/ results/ test-cases/ reports/
│   ├── settings/ users/ errors/ admin/ billing/ …
└── layouts/
```

Zasada: `core` — pojedyncze instancje infrastruktury; `shared` — bez
logiki domenowej; `features` — domeny z własnym routingiem (np.
`features/billing/billing.routes.ts`).

## 2. Shared — komponenty

| Komponent | Rola |
|---|---|
| `navbar.component` | główna nawigacja (menu, dzwonek powiadomień, profil) |
| `footer.component` | stopka |
| `file-upload.component` | drag & drop uploadu z walidacją i progresem (6-2) — sekcja 4 |
| `live-region.component` | region ARIA live dla komunikatów asynchronicznych |
| `notification-bell` | dzwonek powiadomień o progach limitów (E7) |
| `accessibility-toolbar` | pasek dostępności na każdej stronie (kontrast, animacje) — [05 — Motywy](05-motywy-dostepnosci.md) |
| `feature-locked-banner`, `locked-feature-tab`, `locked-module` | blokady modułów poza planem (FR71, widoczne-zablokowane) |
| `quota-exceeded-banner` | banner wyczerpanego limitu (E7) |

## 3. Shared — dyrektywy (dostępność)

| Dyrektywa | Rola |
|---|---|
| `focus-visible.directive` | widoczny fokus klawiaturowy (nie myszowy) |
| `keyboard-nav.directive` | nawigacja klawiaturą po widgetach (strzałki, Home/End) |
| `form-accessibility.directive` | etykiety/opisy pól formularzy dla czytników |
| `heading.directive` | porządek nagłówków (h1–h6 bez przeskoku poziomu) |
| `reduced-motion.directive` | respektowanie redukcji animacji w komponentach |

## 4. Shared — serwisy

| Serwis | Rola |
|---|---|
| `theme.service` | motywy dostępności — sygnały `isHighContrastSignal`/`isReducedMotionSignal`, klasy CSS na `<body>` ([05 — Motywy](05-motywy-dostepnosci.md)) |
| `upload.service` + `file-validation.service` | upload plików, walidacja rozszerzeń/rozmiaru |
| `live-announcer.service` | komunikaty do czytników ekranu (aria-live) |
| `flutter-bridge.service` | mostek do powłoki natywnej (WebView) — [07 — Shell Flutter](07-shell-flutter.md) |
| `notification.service` | powiadomienia in-app (E7) |

## 5. Style i tokeny

`shared/styles/`: `_colors.scss` (paleta), `_focus.scss` (stany fokusu),
`_motion.scss` (animacje + punkty redukcji), `_responsive.scss`
(breakpointy), `_skip-link.scss` (skip-link), `_sr-only.scss` (klasa
dla czytników), `_touch-target.scss` (minimalne rozmiary celów dotykowych),
`themes/_high-contrast.scss` (motyw wysokiego kontrastu).

Tokeny SCSS są jedynym źródłem kolorów/fokusu — komponenty nie definiują
własnych wartości kontrastowych.

## 6. Core — guards i interceptors

- `auth.guard` —Chroni trasy za logowaniem (przekierowanie na `/login`
  z powrotem); `role.guard` — wymóg roli (`Owner`, `Admin`) na trasach
  ustawień użytkowników, panelu admina, bilingu.
- `auth.interceptor` — uwierzytelnienie żądań + obsługa 401 (wylogowanie
  do ekranu logowania); `snake-case.interceptor` — normalizacja pól
  JSON (snake_case ↔ camelCase) przy każdym żądaniu/odpowiedzi.

## 7. Konwencje testowe

Każdy komponent/serwis/guard ma `*.spec.ts` (Vitest przez `ng test`,
builder `@angular/build:unit-test` ze ścisłą type-checką — łapie
regresje interfejsów TS). E2E w `frontend/e2e/` —
[08 — Testy](08-testy.md).
