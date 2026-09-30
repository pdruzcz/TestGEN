# Generowanie przypadków testowych — silnik natywny (Epic 1)

Generowanie scenariuszy testowych na podstawie struktur wyekstrahowanych z AST
([ast-analysis.md](./ast-analysis.md)). Silnik regułowy: klasyfikuje jednostkę
kodową i dobiera szablony scenariuszy (pozytywny, negatywne, brzegowe).

## Klasyfikacja przypadków testowych

Każda funkcja/metoda mapowana na zestaw przypadków zależnie od sygnatury i typu:

| Typ | Kiedy generowany | Cel |
|-----|------------------|-----|
| **Pozytywny** | każda funkcja z Deterministyczną logiką | weryfikacja głównej ścieżki |
| **Negatywny** | funkcje z walidacją wejścia/błędami | weryfikacja obsługi błędów |
| **Brzegowy** | parametry liczbowe/kolekcje | wartości graniczne (0, pusta kolekcja, max) |
| **Integracyjny** | funkcje wołające zewnętrzne serwisły | interakcje między komponentami |

Klasyfikacja typów testu (`unit`/`integration`/`e2e`) i priorytet
(`critical`/`high`/`medium`/`low`) nadawane regułowo.

## Dane testowe i mocki

- **Dane testowe** — generowane na podstawie typów parametrów (primitives,
  kolekcje, stringi z polskimi znakami).
- **Mock obiektów** — dla zależności zewnętrznych wywoływanych przez funkcję
  (rozpoznane z AST).

## Szablony per framework

Kod przypadków generowany przez Jinja2
([ADR-006](../../architecture/adr/ADR-006-jinja2-template-engine.md)) — szczegóły w
[test-code-generation.md](./test-code-generation.md).

## Workflow

Wygenerowane przypadki trafiają ze statusem `draft` i przechodzą przegląd
(`ready` po akceptacji, `passed`/`failed` po wykonaniu) — patrz
[ADR-009](../../architecture/adr/ADR-009-code-review-workflow.md) oraz
[api/examples/test_cases_examples.md](../../architecture/api/examples/test_cases_examples.md).

## Powiązane

- [ast-analysis.md](./ast-analysis.md) — źródło struktur.
- [test-code-generation.md](./test-code-generation.md) — emitowanie kodu.
- [benchmarks.md](./benchmarks.md) — metryki stabilności generatora.
