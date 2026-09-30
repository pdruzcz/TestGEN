# ARIA i czytniki ekranu

> Dokumentacja P2, Epic 6 — Story 6-11.
> Implementacja: dyrektywy `shared/directives/`, `live-region.component`,
> `live-announcer.service`, `i18n/polish-paginator-intl.ts`.

## 1. Zasady użycia ARIA

- **Najpierw semantyka HTML** — ARIA tylko tam, gdzie HTML nie wystarcza
  (widgety kompozytowe, live regions, opisy kontekstowe),
- żadnej informacji tylko-w-kolorze — stan komunikowany tekstem/ikoną
  z etykietą (1.4.1),
- role kompozytowe zgodne z ARIA Authoring Practices (listy wyboru,
  tabele danych z akcjami, dialogi).

## 2. Nawigacja czytnikiem

| Element | Wsparcie |
|---|---|
| Skip-link | „Przejdź do treści" jako pierwszy fokus strony (2.4.1) |
| Nagłówki | dyrektywa `heading` pilnuje hierarchii h1–h6; każda strona ma dokładnie jedno h1 |
| Landmarki | `nav`, `main`, `footer` — nawigacja po regionach |
| Tytuły stron | `title` per trasa (router) — zmiana czytelna w historii i pasku |
| Formularze | `form-accessibility.directive`: etykiety, `aria-describedby` (błędy/podpowiedzi), `aria-invalid` |
| Tabele danych | `th` + `scope`, podpisy (caption), relacje komórka→nagłówek |

## 3. Komunikaty asynchroniczne (aria-live)

- `live-region.component` — wspólny region live w layoucie;
  `live-announcer.service` — API do ogłaszania („Analiza zakończona",
  „Zaznaczono 12 przypadków testowych", błędy operacji),
- priorytet `polite` (nie przerywa czytania), `assertive` tylko dla
  krytycznych błędów blokujących,
- postęp długich operacji (upload, eksport raportu) ogłaszany punktami
  kontrolnymi, nie strumieniem komunikatów.

## 4. Interakcje klawiaturowe widgetów

`keyboard-nav.directive` standaryzuje wzorce: listy/rozwijane — strzałki
góra/dół + Enter/Escape; tabele z akcjami — strzałki między wierszami;
toolbar dostępności — TAB między przełącznikami. Fokus widoczny zawsze
(`_focus.scss` + `focus-visible.directive`).

## 5. Polonizacja komponentów Material

`i18n/polish-paginator-intl.ts` — paginacja Material („Następna strona",
„Pozycje od–do z …") oraz etykiety ikar wskaźników po polsku: czytnik
ekranu nie słyszy angielskich etykiet domyślnych. Wszystkie stringi UI
(aplikacja + komponenty Material + komunikaty błędów HTTP) są po polsku.

## 6. Weryfikacja z czytnikami

- automatycznie: axe-core (E2E) + reguły ARIA w specach komponentowych,
- ręcznie: NVDA (Windows) na przepływach z
  [03 — Mapa ekranów](03-ekrany-i-przeplywy.md) — checklist Story 6-11:
  logowanie, upload, wyniki z filtrami, edycja TC, eksport raportu,
  przełączniki motywów dostępności.
