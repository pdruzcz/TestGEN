# Przewodnik — dostępność w praktyce

> Dokumentacja P2, Epic 6 — Stories 6-9, 6-10, 6-11 (WCAG 2.1 AA).

## 1. Co gwarantuje platforma

Cały interfejs TestGEN spełnia **WCAG 2.1 poziom AA**, m.in.:

- pełna obsługa **klawiatury** (Tab, Enter, Escape, strzałki w listach),
- widoczny **fokus** na każdym elemencie interaktywnym,
- **skip-link** „Przejdź do treści" jako pierwszy element strony,
- kontrasty tekstu ≥ 4,5:1 (wysoki kontrast — nawet 7:1+),
- poprawne etykiety pól i komunikaty błędów (tekstowo, nie tylko
  kolorem),
- działanie przy **zoomie 200%** i szerokości 320 px,
- komunikaty asynchroniczne ogłaszane czytnikom ekranu.

## 2. Wysoki kontrast

Pasek dostępności (ikona na każdym ekranie) → **Wysoki kontrast**:
czarno-biały motyw z kontrastem tekstu co najmniej 7:1 (poziom AAA).
Wybór zapamiętuje się w przeglądarce i działa na wszystkich kolejnych
sesjach. Jeśli system operacyjny ma włączony tryb podwyższonego
kontrastu, TestGEN włączy go automatycznie.

## 3. Redukcja animacji

Pasek dostępności → **Wyłącz animacje**: przejścia i animacje zostają
zastąpione natychmiastowymi zmianami stanu (pomocne przy zawrotach
głowy/migrenach). Ustawienie systemowe „redukuj ruch" jest respektowane
automatycznie, bez żadnej akcji w aplikacji.

## 4. Nawigacja klawiaturą — skróty i wzorce

- **Tab / Shift+Tab** — kolejne elementy (kolejność = kolejność wizualna),
- **Enter/Spacja** — aktywacja przycisku/linku,
- **Escape** — zamknięcie okna dialogowego (fokus wraca na element,
  który je otworzył),
- **strzałki** — poruszanie się po listach, menu i wierszach tabel,
- formularze: błąd pola czytany jest po opuszczeniu pola; lista błędów
  na górze formularza prowadzi do pól.

## 5. Czytniki ekranu

Testowane z NVDA na Windows. Wskazówki:

- struktura nagłówków (poziomy H1–H3) odzwierciedla układ ekranu —
  nawigacja po nagłówkach jest najszybsza,
- landmarki (nawigacja/treść/stopka) dostępne przez skróty regionów,
- zmiany stanu („Analiza zakończona", „Zaznaczono 12 przypadków")
  są ogłaszane automatycznie — nie trzeba szukać ich wzrokiem,
- paginacja i etykiety tabel czytane po polsku.

## 6. Zgłaszanie problemów z dostępnością

Bariera dostępności = błąd produktu. Zgłoś przez obsługę (plan Premium
ma priorytetowe wsparcie); każde zgłoszenie wchodzi na listę Napraw WCAG
i jest weryfikowane testem axe-core po naprawie.
