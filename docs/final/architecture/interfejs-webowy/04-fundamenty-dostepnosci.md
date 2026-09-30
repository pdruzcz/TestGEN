# Fundamenty dostępności — WCAG 2.1 AA

> Dokumentacja P2, Epic 6 — Story 6-9 (fundament, poprzecznie dla całego UI).
> Implementacja: `frontend/src/app/shared/styles/`, dyrektywy w
> `frontend/src/app/shared/directives/`, `live-region.component`.

## 1. Zasada

Dostępność jest wymogiem poprzecznym: **każdy ekran** TestGEN spełnia
WCAG 2.1 poziom AA. Fundamenty (ten rozdział) + motywy
([05](05-motywy-dostepnosci.md)) + ARIA
([06](06-aria-screen-reader.md)) + automatyczny audyt axe-core w CI
([08](08-testy.md)) tworzą pełny łańcuch.

## 2. Warstwa stylów (`shared/styles/`)

| Plik | Zakres | Wymóg WCAG |
|---|---|---|
| `_skip-link.scss` | link „Przejdź do treści" jako pierwszy element strony | 2.4.1 (bypass blocks) |
| `_sr-only.scss` | klasa tekstów tylko dla czytników (`visually-hidden`) | 1.3.1 |
| `_focus.scss` | widoczny ring fokusu na interaktywnych elementach | 2.4.7 (focus visible) |
| `_colors.scss` | paleta z kontrastem tekstu ≥ 4,5:1 i dużego tekstu ≥ 3:1 | 1.4.3 |
| `_touch-target.scss` | minimalne 44×44 px cele dotykowe | 2.5.8 |
| `_motion.scss` | animacje z poszanowaniem `prefers-reduced-motion` | 2.3.3 |
| `_responsive.scss` | breakpointy; layout działa od 320 px szerokości | 1.4.10 (reflow) |

## 3. Semantyka HTML

- Poprawna struktura nagłówków — wymuszana dyrektywą `heading.directive`
  (h1 → h2 → h3 bez przeskakiwania poziomów),
- natywne elementy semantyczne (`nav`, `main`, `table` z `th/scope`,
  `label` powiązany z polem) zamiast div-ów z rolami,
- `lang="pl"` w dokumencie, tytuły stron przez router (`title:` w definicjach
  tras) — każda zmiana widoku aktualizuje `document.title`.

## 4. Klawiatura

- Cała aplikacja obsługiwana z klawiatury (tab, enter, escape, spacja);
  modalne okna Material zamykane Escape i z pułapką fokusu,
- `focus-visible.directive` — fokus podświetlony tylko przy nawigacji
  klawiaturą (nie przy kliku) — pełny kontrast ringu z `_focus.scss`,
- `keyboard-nav.directive` — wzorce nawigacji strzałkami w listach/
  widgetach (np. listy rozwijane, tabele z akcjami) zgodne z
  ARIA Authoring Practices,
- kolejność fokusu zgodna z logiczną kolejnością wizualną (bez dodatkowych
  `tabindex` dodatnich).

## 5. Komunikaty asynchroniczne

`live-region.component` + `live-announcer.service` — zmiany stanu
(postęp analizy, wynik operacji masowej, błędy walidacji) ogłaszane w
regionie aria-live (`polite`), więc czytnik ekranu je przeczyta bez
przenoszenia fokusu. Bannery (limit, blokada modułu) też trafiają do
regionu live przy pojawieniu się.

## 6. Formularze

`form-accessibility.directive` dba o: etykietę każdego pola
(`label for` / `aria-label`), opis błędu powiązany przez `aria-describedby`,
`aria-invalid` przy błędzie i komunikat o błędzie tekstowy (nie tylko
kolor — zasada 1.4.1).

## 7. Weryfikacja

- Automatyczna: axe-core w E2E na kluczowych trasach (próg: **0** naruszeń
  critical/serious — [08 — Testy](08-testy.md)),
- komponentowa: specy a11y przy feature'ach (np. `admin.a11y.spec.ts`,
  `billing.a11y.spec.ts`),
- ręczna: nawigacja klawiaturą + zoom 200% + 320 px (reflow) — checklist
  w specyfikacji Story 6-9.
