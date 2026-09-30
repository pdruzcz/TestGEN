# Specyfikacja Wymagań Oprogramowania

## System Zarządzania Zamówieniami — eShop

**Wersja:** 1.2
**Data:** 2026-05-20
**Autor:** Zespół Analizy Biznesowej

---

## 1. Wprowadzenie

### 1.1 Cel dokumentu

Niniejszy dokument definiuje wymagania funkcjonalne i niefunkcjonalne dla systemu eShop — platformy e-commerce do zarządzania zamówieniami, katalogiem produktów i obsługą klientów.

### 1.2 Zakres

System obejmuje moduły: Katalog Produktów, Koszyk, Zamówienia, Płatności, Konta Użytkowników, Powiadomienia oraz Panel Administracyjny.

### 1.3 Definicje i skróty

| Termin | Definicja |
|--------|-----------|
| SKU | Stock Keeping Unit — unikalny identyfikator produktu |
| BOK | Biuro Obsługi Klienta |
| KPI | Kluczowy Wskaźnik Efektywności |
| SLA | Service Level Agreement — umowa o poziomie usług |
| GDPR | General Data Protection Regulation — ogólne rozporządzenie o ochronie danych |

---

## 2. Wymagania funkcjonalne

### 2.1 Moduł: Konta Użytkowników

#### FR-001: Rejestracja konta

System musi pozwalać nowemu użytkownikowi na rejestrację konta podając adres e-mail, hasło (minimum 8 znaków, wielka litera, cyfra, znak specjalny) oraz imię i nazwisko.

**Kryteria akceptacji:**
- Po rejestracji system wysyła e-mail weryfikacyjny w ciągu 60 sekund
- Konto jest nieaktywne do momentu potwierdzenia e-mail
- Nie można zarejestrować dwóch kont na ten sam e-mail

#### FR-002: Logowanie

Użytkownik może się zalogować przy użyciu e-mail i hasła. Po 5 nieudanych próbach konto jest blokowane na 30 minut.

#### FR-003: Reset hasła

System musi umożliwiać reset hasła poprzez wysłanie unikalnego linku na zarejestrowany adres e-mail. Link jest ważny przez 24 godziny.

#### FR-004: Profil użytkownika

Użytkownik może edytować swoje dane: imię, nazwisko, numer telefonu, adres dostawy. Adresu e-mail nie można zmienić — zamiast tego należy utworzyć nowe konto.

### 2.2 Moduł: Katalog Produktów

#### FR-010: Przeglądanie katalogu

System musi wyświetlać katalog produktów z możliwością filtrowania po kategorii, cenie (zakres), marce oraz ocenach klientów. Domyślne sortowanie to popularność (malejąco).

#### FR-011: Wyszukiwanie produktów

Wyszukiwarka musi zwracać wyniki w czasie poniżej 500 ms dla zapytań do 50 znaków. System musi obsługiwać wyszukiwanie rozmyte (fuzzy search) z tolerancją na 2 literówki.

#### FR-012: Szczegóły produktu

Na stronie produktu wyświetlane są: nazwa, opis, cena brutto, dostępność, specyfikacja techniczna, zdjęcia (minimum 1, maksimum 10) oraz opinie klientów.

#### FR-013: Zarządzanie stanami magazynowymi

System musi automatycznie oznaczać produkty jako „niedostępne", gdy stan magazynowy spadnie do 0. Powiadomienie o niskim stanie (poniżej 10 sztuk) jest wysyłane do administratora.

### 2.3 Moduł: Koszyk

#### FR-020: Dodawanie do koszyka

Użytkownik może dodać produkt do koszyka. Jeśli produkt jest już w koszyku, jego ilość jest zwiększana. Maksymalna ilość jednego produktu w koszyku to 99 sztuk.

#### FR-021: Modyfikacja koszyka

Użytkownik może zmienić ilość produktu, usunąć produkt lub wyczyścić cały koszyk. Ceny w koszyku są aktualizowane na bieżąco zgodnie z aktualną ceną w katalogu.

#### FR-022: Zapis koszyka

Zawartość koszyka jest zapisywana w sesji użytkownika. Po ponownym zalogowaniu koszyk jest przywracany. Koszyk gości (niezalogowanych) jest zachowywany w ciasteczkach przez 7 dni.

### 2.4 Moduł: Zamówienia

#### FR-030: Tworzenie zamówienia

Użytkownik składa zamówienie z koszyka, wybierając adres dostawy i metodę płatności. System przypisuje unikalny numer zamówienia w formacie `ZAM-RRRRMMDD-XXXX` (gdzie XXXX to liczba porządkowa).

#### FR-031: Status zamówienia

Zamówienie przechodzi przez stany: `nowe` → `opłacone` → `w realizacji` → `wysłane` → `dostarczone`. Użytkownik może anulować zamówienie tylko w stanie `nowe`.

#### FR-032: Historia zamówień

Użytkownik ma dostęp do historii wszystkich swoich zamówień z filtrowaniem po dacie, statusie i kwocie. Historia jest przechowywana przez 5 lat od daty ostatniego zamówienia.

#### FR-033: Śledzenie przesyłki

Po zmianie statusu na `wysłane` system generuje link do śledzenia przesyłki i wysyła go e-mailem oraz jako powiadomienie push.

### 2.5 Moduł: Płatności

#### FR-040: Metody płatności

System obsługuje następujące metody płatności: karta płatnicza (Visa, Mastercard), BLIK, przelew bankowy, Google Pay, Apple Pay.

#### FR-041: Bezpieczeństwo płatności

Dane kart płatniczych nie mogą być przechowywane w systemie. Wszystkie transakcje są realizowane przez certyfikowanego operatora płatności (PCI DSS Level 1). Komunikacja z bramką płatności jest szyfrowana (TLS 1.3).

#### FR-042: Zwroty płatności

Zwrot środków jest realizowany w ciągu 14 dni roboczych od zatwierdzenia reklamacji. Zwrot jest księgowany na tę samą metodę płatności, której użyto przy zakupie.

### 2.6 Moduł: Powiadomienia

#### FR-050: Kanały powiadomień

System wysyła powiadomienia przez trzy kanały: e-mail, SMS i push (przeglądarka). Użytkownik może skonfigurować preferencje powiadomień w ustawieniach konta.

#### FR-051: Szablony powiadomień

Powiadomienia e-mail są wysyłane z szablonów HTML zgodnych z zasadami dostępności WCAG 2.1 AA. Szablony są edytowalne przez administratora.

---

## 3. Wymagania niefunkcjonalne

### 3.1 Wydajność

#### NFR-001: Czas odpowiedzi

Czas odpowiedzi strony nie może przekroczyć 2 sekundy dla 95% żądań przy obciążeniu do 1000 jednoczesnych użytkowników.

#### NFR-002: Dostępność

System musi utrzymywać dostępność na poziomie minimum 99,9% w ujęciu miesięcznym (maksymalnie 43 minuty przerwy miesięcznie).

#### NFR-003: Skalowalność

Architektura musi pozwalać na poziome skalowanie — dodanie węzła aplikacyjnego nie może wymagać przerwy w działaniu systemu.

### 3.2 Bezpieczeństwo

#### NFR-010: Uwierzytelnianie

Hasła muszą być hashowane algorytmem Argon2id z parametrami: memory=64MB, iterations=3, parallelism=4.

#### NFR-011: Sesje

Tokeny sesyjne (JWT) mają ważność 15 minut dla tokenu dostępu i 7 dni dla tokenu odświeżającego. Tokeny są przesyłane w ciasteczkach HttpOnly + Secure + SameSite=Strict.

#### NFR-012: Ochrona danych

Dane osobowe muszą być szyfrowane w spoczynku (AES-256) i w tranzycie (TLS 1.3). System musi spełniać wymogi RODO/GDPR, w tym prawo do bycia zapomnianym.

### 3.3 Niezawodność

#### NFR-020: Kopie zapasowe

Baza danych jest backupowana codziennie o 02:00. Backupy są przechowywane przez 30 dni w lokalizacji geograficznie oddalonej.

#### NFR-021: Disaster recovery

RTO (Recovery Time Objective) nie może przekroczyć 4 godzin. RPO (Recovery Point Objective) nie może przekroczyć 1 godziny.

---

## 4. Wymagania interfejsu

### 4.1 Responsywność

Interfejs musi być responsywny i prawidłowo wyświetlać się na urządzeniach o szerokości ekranu od 320px (smartfon) do 2560px (monitor 2K).

### 4.2 Dostępność

Interfejs musi spełniać standard WCAG 2.1 poziom AA, w tym: wsparcie dla czytników ekranu, nawigacja klawiaturą, minimalny kontrast tekstu 4.5:1.

---

## 5. Ograniczenia i założenia

1. System obsługuje wyłącznie język polski i angielski
2. Waluta domyślna to PLN (polski złoty)
3. System jest dostępny 24/7 z wyjątkiem okna technicznego: niedziela 03:00–05:00 CET
4. Maksymalny rozmiar przesyłanego pliku to 10 MB
5. System jest kompatybilny z przeglądarkami: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+

---

## 6. Historia zmian

| Wersja | Data | Autor | Opis zmiany |
|--------|------|-------|-------------|
| 1.0 | 2026-03-01 | J. Kowalski | Wersja początkowa |
| 1.1 | 2026-04-15 | M. Nowak | Dodano moduł powiadomień i wymagania NFR |
| 1.2 | 2026-05-20 | A. Wiśniewski | Dodano FR-040 do FR-042 (płatności), zaktualizowano NFR-011 |

---

*Autor: Zespół Analizy Biznesowej, Nexio Management Sp. z o.o.*
*Kontakt: analizy@nexio-management.pl*
