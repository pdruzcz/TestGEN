# Przewodnik — projekty i upload plików

> Dokumentacja P2, Epic 6 — Stories 6-1, 6-2, 6-3.

## 1. Tworzenie projektu

Na `/projects` przycisk nowego projektu: nazwa i opis. Projekt jest
przestrzenią roboczą dla analiz jednej aplikacji — pliki, wyniki,
test case'y i raporty żyją w obrębie projektu. Usunięcie projektu
(wymaga potwierdzenia w dialogu) usuwa powiązane dane.

## 2. Upload plików (drag & drop)

Ekran plików projektu (`/projects/{id}/files` i upload dokumentacji):

1. **Przeciągnij pliki** na obszar przesyłania albo wybierz je
   przyciskiem — można wiele plików naraz.
2. Pliki są sprawdzane od razu: **dozwolone rozszerzenia** i **limit
   rozmiaru** (błędne pliki są oznaczane przed startem przesyłania —
   nic nie „wisi" na serwerze).
3. Upload biegnie **równolegle**, każdy plik ma własny pasek postępu
   i status: oczekuje → przesyłanie → OK / błąd / anulowano.
4. Podsumowanie pokazuje ile plików wgrano, ile nie udało się —
   i dlaczego; błędne można powtórzyć bez wgrywania od nowa całości.

Uwagi: limit plików na analizę zależy od planu (5/25/50 —
`docs/final/user-guide/billing/`); upload może zostać odrzucony przez limit
storage tenanta (banner z wyjaśnieniem).

## 3. Dokumenty i źródła projektu

Zakładki projektu prowadzą do poszczególnych źródeł analizy: kod
(pliki), dokumentacja (`/documents` — upload i podgląd), diagramy UML,
zrzuty GUI. Każde źródło pokazuje status przetworzenia (np. raport
preprocessingu dokumentacji przed uruchomieniem analizy).

## 4. Uruchomienie analizy

1. Zakładka **Analiza** projektu — wybierz źródła i rodzaj analizy.
2. Uruchom — postęp zadania widać na ekranie; zakończenie ogłasza
   komunikat (działa też z czytnikiem ekranu).
3. Wyniki analizy pojawiają się w przeglądarce wyników — patrz
   [03 — Wyniki i test case'y](03-wyniki-i-test-case-y.md).

Analiza zużywa limit planu (licznik „Analizy"); przy braku limitu
system poinformuje błędem z podpowiedzią zmiany planu.

## 5. Porządkowanie

- Filtr listy projektów na dashboardzie (nazwa, status, data),
- historia analiz projektu zachowuje wyniki do porównań między
  uruchomieniami,
- stare pliki można usuwać, by odzyskać limit storage.
