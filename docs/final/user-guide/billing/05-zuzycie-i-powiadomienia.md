# Przewodnik — zużycie zasobów i powiadomienia

> Dokumentacja P2, Epic 7 — Stories 7.9, 7.11.
> Ekran: `/billing/usage` (wszyscy użytkownicy tenanta).

## 1. Dashboard zużycia

Ekran pokazuje karty liczników z paskami postępu:

| Licznik | Co mierzy | Limit Freemium/Basic/Premium |
|---|---|---|
| Analizy | analizy uruchomione w bieżącym okresie | 10 / 50 / bez limitu |
| Test case'y | wygenerowane przypadki testowe | 50 / 250 / bez limitu |
| Storage | miejsce na pliki | 0,5 / 5 / 10 GB |
| Pliki na analizę | pliki w jednej analizie | 5 / 25 / 50 |

Na każdej karcie: zużycie, limit, procent, dni do końca okresu
rozliczeniowego. Rozwinięcie karty pokazuje **wykres historii**
dziennego zużycia (natywny wykres SVG).

## 2. Prognoza wyczerpania limitu

Gdy system ma co najmniej 7 dni danych o Twoim zużyciu, na karcie
pojawia się **ostrzeżenie prognozy**: przy obecnej średniej dziennego
zużycia limit zostanie wyczerpany **przed końcem okresu rozliczeniowego**
(z informacją, na który dzień). To sygnał, by zawczasu podnieść plan —
upgrade działa natychmiast (patrz [02 — Zarządzanie subskrypcją](02-zarzadzanie-subskrypcja.md)).

## 3. Powiadomienia o progach

Gdy zużycie któregoś licznika przekroczy **80%**, **90%** lub **100%**
limitu:

- **w aplikacji** — dzwonek w navbarze z licznikiem nieprzeczytanych;
  lista powiadomień z akcją „oznacz wszystkie jako przeczytane",
- **mailem** — jeśli nie wyłączysz tego kanału w ustawieniach profilu
  (preferencje kanałów: in-app / email).

Każdy próg informuje maksymalnie raz w okresie rozliczeniowym — bez
spamowania przy kolejnych godzinowych sprawdzeniach.

## 4. Co się dzieje po wyczerpaniu limitu

- Liczniki analiz/test case'ów/plików: kolejna operacja zwraca komunikat
  o wyczerpanym limicie (HTTP 402/429) z podpowiedzią zmiany planu lub
  odczekania do końca okresu. Liczniki **resetują się** na początku
  nowego okresu rozliczeniowego.
- Storage: upload nowych plików zablokowany do zwolnienia miejsca
  (usunięcie starych analiz) lub zmiany planu.
- Zużycie liczników nie jest cofane po downgrade — obowiązują limity
  nowego planu od momentu jego wejścia w życie.

## 5. Widoczność

Dashboard zużycia i powiadomienia dotyczą **całego tenanta** (limity są
per firma, nie per użytkownik) — każdy użytkownik widzi te same wartości.
