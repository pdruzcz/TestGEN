# Przewodnik — faktury i dane fakturowe

> Dokumentacja P2, Epic 7 — Story 7.6.
> Ekrany: `/billing/invoices` (Owner i User), `/billing/invoice-data` (Owner).

## 1. Faktury

Po **każdej opłaconej płatności** (zakup, upgrade, odnowienie) system
automatycznie wystawia fakturę VAT i wysyła ją mailem do Ownera z PDF
w załączniku. Lista faktur (`/billing/invoices`) zawiera: numer
(`FV/rok/miesiąc/sekwencja`), datę wystawienia, kwotę brutto, metodę
płatności i status. Przycisk pobrania zwraca PDF.

Faktura zawiera: numer, daty wystawienia i sprzedaży, dane sprzedawcy
(TestGEN) i nabywcy (snapshot danych fakturowych z chwili wystawienia),
pozycję z opisem planu i okresem, kwoty netto/VAT 23%/brutto w PLN.

## 2. Dane fakturowe (Owner)

Ekran `/billing/invoice-data` pozwala wpisać dane do faktur: nazwa firmy,
NIP, adres. Przy pierwszym wejściu formularz inicjalizuje się danymi
profilu tenanta.

**Ważne**: zmiana danych dotyczy wyłącznie **następnych** faktur —
wystawione faktury przechowują snapshot danych z chwili wystawienia
(wymóg księgowy). Chcesz poprawić dane na już wystawionej fakturze —
skontaktuj się z obsługą (faktura korygująca po stronie księgowości).

## 3. Kiedy faktura może nie przyjść mailem?

Faktura powstaje w tle po webhooku płatności — email z PDF może
dotrzeć z krótkim opóźnieniem (do kilku minut). Email nie dotarł, a
płatność się udała? PDF jest zawsze dostępny na liście faktur —
wysyłka mailowa jest tylko dodatkiem, nie warunkiem wystawienia.

## 4. History transakcji

Ekran `/billing/transactions` (Owner i User) — pełna historia płatności:
data, kwota, plan, status (np. oczekująca/zakończona/nieudana), metoda.
Filtry statusu i zakresu dat + paginacja. Tu sprawdzisz też płatności,
które nie powiodły się (np. odrzucony upgrade) — z kwotą i statusem.
