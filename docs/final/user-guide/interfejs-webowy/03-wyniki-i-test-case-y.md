# Przewodnik — wyniki analiz i test case'y

> Dokumentacja P2, Epic 6 — Stories 6-4, 6-5.

## 1. Przeglądarka wyników

Zakładka **Wyniki** projektu (`/projects/{id}/results`):

- **Panel filtrów** — zawężanie po typie znaleziska, wadze (severity),
  statusie, module; filtry działają bez przeładowania,
- **szczegóły znaleziska** — opis, kontekst, źródło,
- **podświetlanie kodu** — fragmenty kodu z zachowaną składnią,
- **diff viewer** — porównanie wersji obok siebie (np. rozbieżność kod ↔
  dokumentacja).

Te same komponenty obsługują wyniki wszystkich modułów analiz
(dokumentacja, UML/GUI, bezpieczeństwo, luki funkcjonalne) — uczysz się
ich raz.

## 2. Zarządzanie test case'ami

Zakładka **Test case'y** (`/projects/{id}/test-cases`) — kompletny widok
zarządzania wygenerowanymi przypadkami testowymi:

| Czynność | Jak |
|---|---|
| Przegląd | tabela TC projektu z filtrowaniem grupowym; wejście do szczegółów |
| Edycja | edytor TC — kroki, oczekiwane rezultaty, priorytet |
| Operacje masowe | pasek akcji masowych: zmiana statusu, eksport, usunięcie zaznaczonych |
| Historia | dialog historii zmian TC (kto, co, kiedy) |
| Eksport do TMS | dialog eksportu — **CSV lub XML** do zaimportowania w narzędziu TMS (TestRail, Xray…) |
| Import | mapowanie pól przy imporcie TC z zewnątrz |

Zmiany zapisują się automatycznie; komunikat potwierdzenia czyta się
także w czytniku ekranu.

## 3. Statusy i priorytety

Test case'y mają statusy (np. szkic → zaakceptowany → archiwalny) —
przydają się przy przeglądzie wygenerowanych treści przed użyciem.
Operacje masowe pozwalają zaakceptować całą paczkę po weryfikacji.

## 4. Limity

Generowanie test case'ów zżyna limit planu (50/250/bez limitu miesięcznie).
Licznik zużycia — dashboard zużycia (`/billing/usage`,
`docs/final/user-guide/billing/`).
