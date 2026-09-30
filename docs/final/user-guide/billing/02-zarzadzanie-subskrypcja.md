# Przewodnik — zarządzanie subskrypcją

> Dokumentacja P2, Epic 7 — Stories 7.5, 7.7.
> Ekran: `/billing/subscription` (navbar → „Subskrypcja", rola **Owner**).

## 1. Szczegóły subskrypcji

Ekran pokazuje: plan z ceną, status, okres rozliczeniowy (start/koniec),
metodę płatności (wizerunek karty/aliasu), datę najbliższego obciążenia
oraz — gdy liczy się czas — zaplanowaną zmianę planu albo anulowanie.

## 2. Zmiana planu (FR55)

Przycisk zmiany planu prowadzi przez potwierdzenie
(`plan-change-confirm.component`) z **podglądem kwoty** — obliczonej
proration:

- **Upgrade** (np. Basic → Premium): dopłata proporcjonalna do pozostałych
  dni bieżącego okresu. Przy kwocie > 0 następuje przekierowanie na panel
  tpay (płatność jak przy zakupie); przy kwocie 0,00 (np. ostatni dzień
  okresu) — zmiana natychmiastowa, bezpłatna. Nowy plan obowiązuje od
  razu po opłaceniu.
- **Downgrade** (np. Premium → Basic): **bez płatności** — nowy plan
  zaczyna obowiązywać **na koniec bieżącego okresu**; do tego czasu
  korzystasz z obecnego planu. Rozliczenie następuje na koniec okresu,
  bez zwrotów.
- Z Freemium: pełna cena pierwszego miesiąca nowego planu.

Zaplanowany downgrade możesz **odwołać** do końca okresu przyciskiem
rezygnacji — subskrypcja wraca do bieżącego planu i odnowienia.

### Historia zmian

Sekcja/ekran historii (`subscription/history` w API) pokazuje pełny audyt:
typ zmiany, plany z→na, status (zaplanowana / oczekuje na płatność /
zakończona / nieudana / odwołana), kwotę i szczegóły proration.
Nieudany upgrade (odrzucona płatność) nie zmienia planu — rekord z
statusem „nieudana" + email wyjaśniający.

## 3. Anulowanie subskrypcji

1. Na `/billing/subscription` kliknij **Anuluj subskrypcję**.
2. Dialog potwierdzenia (`cancel-confirm-dialog.component`) wyjaśnia
   konsekwencje: dostęp do planu **do końca opłaconego okresu**, potem
   automatyczny powrót do Freemium (limit 10 analiz/mies., 0,5 GB…).
3. Potwierdzenie jest operacją lokalną — karta/alias nie są obciążane,
   żadne wywołanie do tpay nie następuje.

Anulowanie przy zaplanowanym downgrade'u: działa jak zwykle — na koniec
okresu obowiązuje **plan niższy** z downgrade'u (nie Freemium).
Anulowanie na Freemium → 409 (nie ma czego anulować); ponowne
anulowanie → 409.

## 4. Reaktywacja

Przed końcem okresu po anulowaniu możesz kliknąć **Reaktywuj**: zdjęcie
flagi anulowania, przywrócenie najbliższego obciążenia na koniec
bieżącego okresu — kontynuacja bez przerwy i bez ponownej płatności.
Reaktywacja przy oczekującej zmianie planu → 409 (najpierw rozstrzygnij
zmianę: odwołaj ją lub zaczekaj na jej wykonanie).

## 5. Nieudane odnowienie (dunning)

Gdy odnowienie nie może obciążyć metody płatności:

1. System ponawia próby w kolejnych dniach (`dunning`); na bieżąco
   informuje mailem.
2. Po wyczerpaniu prób: downgrade do **Freemium** + **7 dni okresu
   łaski (grace)** z zachowaniem limitów płatnego planu — czas na
   aktualizację metody płatności (patrz
   [03 — Metody płatności](03-metody-platnosci.md)).
3. Po upływie grace obowiązują limity Freemium. Konto ani dane nie są
   blokowane; powrót na plan płatny = normalny zakup.

Najczęstsze przyczyny: wygasła karta, przekroczony limit aliasu BLIK
(12 płatności — po jego wyczerpaniu zapłać ponownie, co utworzy nowy
alias), usunięcie metody płatności (system blokuje usunięcie jedynej
metody przy aktywnej subskrypcji — 409).
