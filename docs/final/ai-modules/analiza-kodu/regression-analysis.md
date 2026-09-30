# Analiza regresji na podstawie diff AST (Epic 1)

Wykrywanie, które fragmenty kodu uległy zmianie między dwiema wersjami analizy,
i determinacja, które przypadki testowe należy uruchomić ponownie. Podłoże:
buforowana analiza AST ([ast-analysis.md](./ast-analysis.md)).

## Diff struktur

Porównanie dwóch analiz (`logic_structures`) klasyfikuje każdą jednostkę:

| Zmiana | Opis |
|--------|------|
| **added** | nowa funkcja/klasa — brak pokrycia testami |
| **removed** | usunięta jednostka — powiązane testy do weryfikacji/usunięcia |
| **changed** | zmieniona sygnatura/ciało — testy do ponownego uruchomienia |
| **unchanged** | brak zmiany — testy mogą zostać pominięte (przyspieszenie) |

## Selekcja testów regresyjnych

Na podstawie diff generowany jest **zestaw regresyjny** — przypadki testowe
powiązane ze zmienionymi/nowymi strukturami. Niezmienione obszary są pomijane,
co skraca czas wykonania przy dużych bazach kodu.

## Testy regresyjne i golden data

Stabilność wyjścia analizy walidowana golden data
([ADR-008](../../architecture/adr/ADR-008-golden-data.md)): zmiana kodu psująca deterministyczne
wyjście AST/klasyfikacji zostaje wychwycona przez testy bramkowe.

## Powiązane

- [ast-analysis.md](./ast-analysis.md) — źródło diff.
- [ADR-008](../../architecture/adr/ADR-008-golden-data.md) — detekcja regresji.
- [benchmarks.md](./benchmarks.md) — metryki stabilności.
