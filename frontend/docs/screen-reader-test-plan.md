# Plan testów screen readera (NVDA) — Story 6.11 (WCAG 2.1 AA)

Plan manualnych testów dostępności aplikacji TestGEN z użyciem czytnika ekranu
NVDA na Windows 11. Cel (AC5): **0 blockerów, maksymalnie 2 minor issues**
w kluczowych flow.

## Środowisko testowe

| Element        | Wartość                                          |
| -------------- | ------------------------------------------------ |
| Czytnik ekranu | NVDA (najnowsza stabilna, https://www.nvaccess.org/) |
| System         | Windows 11                                       |
| Przeglądarki   | Chrome (podstawowa), Firefox (weryfikacja)       |
| Język NVDA     | polski (synteza + interfejs)                     |
| Aplikacja      | `ng serve` (http://localhost:4200) lub środowisko testowe |

## Klasyfikacja problemów

- **Blocker** — użytkownik screen readera nie może ukończyć zadania
  (np. nieosiągalny przycisk, brak ogłoszenia krytycznego błędu, pułapka fokusu
  poza dialogiem, nieopisany element formularza).
- **Minor** — zadanie wykonalne, ale doświadczenie jest gorsze
  (np. nadmiarowe ogłoszenia, nieoptymalna kolejność czytania, brakująca
  etykieta elementu dekoracyjnego).

Każdy problem dokumentujemy w tabeli wyników: strona/krok, opis, klasyfikacja,
rekomendacja naprawy.

## Skróty NVDA używane w testach

| Skrót              | Działanie                          |
| ------------------ | ---------------------------------- |
| `D` / `Shift+D`    | następny/poprzedni landmark        |
| `H` / `1`–`6`      | nawigacja po nagłówkach            |
| `T`                | następna tabela                    |
| `Ctrl+Alt+strzałki`| nawigacja po komórkach tabeli      |
| `F`                | następne pole formularza           |
| `B`                | następny przycisk                  |
| `Insert+F7`        | lista elementów (linki/nagłówki)   |
| `Insert+Space`     | przełączanie trybu formularza      |

## Testy przekrojowe (każda strona)

1. **Skip link** — pierwszy `Tab` na stronie ogłasza „Przejdź do treści
   głównej"; `Enter` przenosi fokus do `<main id="main-content">`.
2. **Landmarki** (`D`) — obecne i ogłaszane: banner (header z nawigacją),
   navigation „Menu główne", main, contentinfo (footer z logotypami).
3. **Nagłówki** (`H`, `Insert+F7`) — dokładnie jedna `h1` na stronę,
   hierarchia sekwencyjna bez pomijania poziomów (h1 → h2 → h3).
4. **Ikony** — przyciski z samą ikoną ogłaszają polską etykietę
   (np. „Zamknij", „Usuń", „Wyloguj się"); ikony dekoracyjne pomijane.
5. **Spinnery / progress bary** — ogłaszane z etykietą
   (np. „Ładowanie", „Postęp analizy").

## Scenariusze — kluczowe flow

### Flow 1: Logowanie (`/login`)

| # | Krok | Oczekiwany rezultat |
| - | ---- | ------------------- |
| 1 | Wejdź na `/login`, czytaj od góry | Tytuł strony i h1 ogłoszone; formularz osiągalny przez `F` |
| 2 | Nawiguj po polach e-mail/hasło | Każde pole ogłasza etykietę, typ i stan wymagalności |
| 3 | Przełącz widoczność hasła | Przycisk-ikona ma polską etykietę i ogłasza zmianę stanu |
| 4 | Wyślij pusty formularz | Błędy walidacji ogłaszane (aria-live/rola alert), powiązane z polami przez aria-describedby, pola z aria-invalid |
| 5 | Wpisz błędne dane i zaloguj | Komunikat błędu ogłaszany asertywnie |
| 6 | Zaloguj poprawnie | Przekierowanie na dashboard; fokus/tytuł nowej strony zrozumiały |

### Flow 2: Upload dokumentu (`/projects/:id/upload`)

| # | Krok | Oczekiwany rezultat |
| - | ---- | ------------------- |
| 1 | Przejdź do projektu → upload | Landmarki i h1 poprawne |
| 2 | Wybierz plik (przycisk / input) | Kontrolka wyboru pliku osiągalna i opisana |
| 3 | Rozpocznij upload | Postęp ogłaszany (progress bar z etykietą, aria-live polite) |
| 4 | Zakończenie / błąd uploadu | Sukces ogłaszany polite, błąd assertive |
| 5 | Usuń plik z listy | Przycisk „Usuń" ma etykietę z kontekstem, potwierdzenie ogłaszane |

### Flow 3: Konfiguracja analizy (`/projects/:id/analysis`)

| # | Krok | Oczekiwany rezultat |
| - | ---- | ------------------- |
| 1 | Otwórz konfigurację analizy | h1 + landmarki poprawne |
| 2 | Nawiguj po opcjach (checkboxy/selecty) | Każda opcja ogłasza etykietę i stan (zaznaczone/nie) |
| 3 | Uruchom analizę | Zmiana statusu ogłaszana (aria-live), spinner z etykietą |
| 4 | Postęp analizy | Progress bar ogłaszany z etykietą „Postęp analizy" |

### Flow 4: Przeglądanie wyników (`/projects/:id/results`)

| # | Krok | Oczekiwany rezultat |
| - | ---- | ------------------- |
| 1 | Otwórz listę wyników | Tabela osiągalna przez `T`, caption ogłaszany |
| 2 | Nawiguj po komórkach (`Ctrl+Alt+strzałki`) | NVDA czyta nagłówek kolumny + wartość komórki (scope="col") |
| 3 | Filtruj / sortuj | Kontrolki filtrów opisane; zmiana wyników ogłaszana |
| 4 | Otwórz szczegół wyniku | Fokus trafia do szczegółu / dialog z focus trap |
| 5 | Zamknij dialog (Escape) | Dialog zamknięty, fokus wraca do elementu wyzwalającego |

### Flow 5: Generowanie raportu (`/projects/:id/reports`)

| # | Krok | Oczekiwany rezultat |
| - | ---- | ------------------- |
| 1 | Otwórz stronę raportów | h1 + landmarki poprawne |
| 2 | Konfiguruj raport (format, zakres) | Pola formularza opisane |
| 3 | Generuj / eksportuj | Dialog postępu: role="dialog", aria-modal, focus trap; postęp ogłaszany („Postęp eksportu") |
| 4 | Pobierz plik | Przycisk pobierania opisany; sukces ogłaszany |

### Flow 6: Dialogi (przekrojowo, AC6)

| # | Krok | Oczekiwany rezultat |
| - | ---- | ------------------- |
| 1 | Otwórz dowolny MatDialog | Ogłoszony tytuł dialogu (aria-labelledby z mat-dialog-title), role="dialog", aria-modal="true" |
| 2 | `Tab` / `Shift+Tab` w dialogu | Fokus zapętlony wewnątrz dialogu (CDK focus trap) |
| 3 | `Escape` | Dialog zamknięty, fokus wraca do triggera |

## Raport wyników (do wypełnienia po sesji testowej)

| Data | Tester | NVDA | Przeglądarka | Blockery | Minor |
| ---- | ------ | ---- | ------------ | -------- | ----- |
|      |        |      |              |          |       |

### Znalezione problemy

| # | Flow/strona | Opis | Klasyfikacja | Rekomendacja naprawy | Status |
| - | ----------- | ---- | ------------ | -------------------- | ------ |
|   |             |      |              |                      |        |

**Kryterium zaliczenia (AC5):** 0 blockerów, maksymalnie 2 minor issues.
Każdy blocker wymaga naprawy i retestu przed zamknięciem story.
