# Przewodnik — plany i zakup subskrypcji

> Dokumentacja P2, Epic 7. Ekran: `/billing/plans` (menu „Rozliczenia").

## 1. Porównanie planów

Ekran **Plany subskrypcji** (`plan-comparison.component`) pokazuje trzy
plany z cenami miesięcznymi: Freemium (0 PLN), Basic (30 PLN), Premium
(50 PLN). Macierz różnic:

- limity: analizy/miesiąc (10/50/bez limitu), test case'y (50/250/bez
  limitu), storage (0,5/5/10 GB), pliki na analizę (5/25/50),
- moduły analizy: analiza kodu i generowanie testów — wszystkie plany;
  dokumentacja, UML, GUI, testy integracyjne, CI/CD — Basic;
  bezpieczeństwo, rekomendacje bezpieczeństwa, spójność kod↔dokumentacja,
  luki funkcjonalne — Premium,
- priorytetowe wsparcie — Premium.

Aktualny plan tenanta jest wyróżniony. Ceny są miesięczne — nie ma
płatności rocznych.

## 2. Zakup planu (Owner)

1. Upewnij się, że masz rolę **Owner** (zakup wymaga Ownera; User widzi
   plany, ale nie kupuje).
2. Na `/billing/plans` kliknij **Wybierz Basic/Premium**.
3. Zostaniesz przekierowany na **Panel Transakcyjny tpay**:
   - BLIK, karta (z 3-D Secure) albo przelew/PBL — metoda wybierasz
     w panelu tpay,
   - regulamin i polityka prywatności są dostępne na stronach zakupu
     (linki test-gen.pl).
4. Po płatności wracasz na `/billing/checkout/success` — strona sama
   odpytuje status transakcji i pokazuje potwierdzenie; aktywnacja planu
   następuje po webhooku od tpay (zwykle w ciągu sekund).
5. Potwierdzenie zakupu przychodzi też mailem; faktura VAT — patrz
   [04 — Faktury i dane fakturowe](04-faktury-i-dane-fakturowe.md).

### Pierwsza płatność BLIK = metoda odnowień

Płacąc BLIK, wyrażasz zgodę na **Płatności Powtarzalne** — tworzony jest
alias BLIK, którym odnowienia będą obciążane automatycznie co miesiąc
(limit pojedynczej płatności = cena planu). Jeśli Twój bank nie obsługuje
tej usługi, system zaproponuje płatność kartą i zapisanie jej jako metody
odnowień.

### Gdy coś pójdzie nie tak

- Odrzucenie płatności → `/billing/checkout/error` z przyczyną i przyciskiem
  ponowienia (transakcja lokalna zostaje anulowana — nic nie kosztuje).
- Dłuższe „wisi" statusu → strona sama dopyta tpay o rzeczywisty stan
  (reconciliation); ostatecznym źródłem prawdy jest webhook.
- Błąd techniczny (502) → spróbuj ponownie za chwilę.

## 3. Moduły zablokowane planem

Moduły analizy poza planem są widoczne w UI, ale z kłódką i podpisem,
który plan je odblokowuje — po wejściu pojawia się komunikat 402 z CTA
do porównania planów. Po zakupie wyższego planu moduły odblokowują się
bez przeładowania strony. Szczegóły: [05 — Zużycie i powiadomienia](05-zuzycie-i-powiadomienia.md).

## 4. Zmiana planu

Zmiana planu (upgrade/downgrade) przy aktywnej subskrypcji płatnej
odbywa się przez ekran **Subskrypcja** — patrz
[02 — Zarządzanie subskrypcją](02-zarzadzanie-subskrypcja.md).
Bezpośredni zakup (`/billing/checkout`) dotyczy tylko przejścia
z Freemium na plan płatny.
