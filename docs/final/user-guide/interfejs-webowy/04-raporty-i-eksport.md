# Przewodnik — raporty i eksport

> Dokumentacja P2, Epic 6 — Stories 6-6, 6-7 (FR43–FR45).

## 1. Raporty dwupoziomowe

Zakładka **Raporty** projektu (`/projects/{id}/reports`) generuje raport
z wyników analizy w dwóch warstwach:

- **Executive summary** — dla zarządu/interesariuszy: podsumowanie
  jakości, metryki zagregowane, najważniejsze ryzyka; bez żargonu,
- **szczegóły techniczne** — dla zespołów QA/dev: pełne listy znalezisk
  z kontekstem, odwołania do kodu.

Obie warstwy powstają z tego samego zbioru wyników — różni je układ
i poziom szczegółowości. Podgląd na ekranie pokazuje dokładnie to, co
trafi do pliku.

## 2. Formaty eksportu

Przyciski eksportu generują plik w formacie: **PDF, HTML, CSV, Excel,
JSON, YAML**. Dłuższe eksporty pokazują dialog postępu (anulowalny);
ukończenie jest ogłaszane komunikatem. Wykresy w raportach renderują
się niezależnie od przeglądarki — plik wygląda tak samo wszędzie.

Wybór formatu w praktyce:

| Format | Kiedy |
|---|---|
| PDF | do wysyłki/archiwizacji, wersja do druku |
| HTML | podgląd w przeglądarce, intranet |
| CSV / Excel | dalsza analiza w arkuszu |
| JSON / YAML | wrzutka do narzędzi/pipeline'ów |

## 3. Eksport test case'ów do TMS

Osobny eksport z widoku test case'ów (CSV/XML — patrz
[03 — Wyniki i test case'y](03-wyniki-i-test-case-y.md)) — plik
importujesz w swoim narzędziu do zarządzania testami.

## 4. Powiązania

- Wyniki w raportach pochodzą z przeglądarki wyników — te same filtry
  i statusy,
- raporty można porównywać między analizami (zakładka porównań
  projektu) — szczegóły w dokumentacjach modułów (np. luki
  funkcjonalne),
- ekrany raportów spełniają WCAG 2.1 AA — eksport PDF zachowuje
  kontrasty i strukturę nagłówków.
