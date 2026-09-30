# Przewodnik — metody płatności

> Dokumentacja P2, Epic 7 — Stories 7.2, 7.7.
> Ekran: `/billing/payment-methods` (rola **Owner**).

## 1. Lista metod

Ekran pokazuje zapisane metody płatności:

- **karty** — wizerunek (ostatnie 4 cyfry, marka, np. `•••• 4242 Visa`),
  data ważności, status (aktywna / w trakcie rejestracji / usunięta),
  metoda domyślna odnowień,
- **aliasy BLIK** (Płatności Powtarzalne) — tworzony automatycznie przy
  pierwszej płatności BLIK; ważność do 730 dni, limit 12 płatności.

Statusy kart odświeżają się na żywo z tpay (krótki cache 5 min); gdy
tpay jest chwilowo niedostępny, pokazujemy ostatni znany stan.

## 2. Dodanie karty (bez obciążenia)

1. Kliknij **Dodaj kartę** — zostaniesz przekierowany do panelu tpay.
   Karta jest zapisywana **bez żadnej płatności** (rejestracja tokena).
2. Po powrocie (`/billing/payment-methods/return`) strona sama sprawdza
   potwierdzenie — nowa karta pojawia się na liście jako aktywna.
3. Kartę ustawisz jako domyślną metodę odnowień.

Karta przechowywana jest wyłącznie u tpay (token); TestGEN trzyma token
zaszyfrowany i wizerunek karty — nigdy pełny numer.

## 3. Usuwanie metody

Przycisk usuwania przy metodzie: karta/alias jest usuwany także u tpay.
**Ostrzeżenie 409**: nie można usunąć jedynej aktywnej metody, gdy
subskrypcja odnawia się cyklicznie — najpierw dodaj inną metodę.

## 4. Która metoda płaci przy odnowieniu

- Jeśli ustawiona jest metoda domyślna (karta) — odnowienie obciąża ją.
- Alias BLIK obciążany jest automatycznie, dopóki jest aktywny i ma
  niewyczerpany limit płatności.
- Brak aktywnej metody przy odnowieniu → dunning (ponawiane próby,
  ostatecznie Freemium + 7 dni grace — patrz
  [02 — Zarządzanie subskrypcją](02-zarzadzanie-subskrypcja.md), sekcja 5).

## 5. Bank nie obsługuje Płatności Powtarzalnych

Przy zakupie BLIK część banków odmawia (błąd `refusenopayid`) — wtedy
system podpowie: zapłać **kartą** i **zapisz ją jako metodę płatności**;
odnowienia będą obciążać kartę. Płatność jednorazowa BLIK nadal działa —
bez funkcji automatycznego odnowienia.
