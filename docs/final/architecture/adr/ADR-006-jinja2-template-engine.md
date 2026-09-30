# ADR-006: Jinja2 jako silnik szablonów kodu testowego

## Status

Accepted

## Kontekst

Generowany kod testów musi być spójny stylistycznie, zawierać poprawne importy,
wzorce asercji i konwencje danego frameworka. Bez ujednoliconego podejścia
wygenerowane testy są niespójne i często niegotowe do uruchomienia.

## Decyzja

Generowanie kodu testowego oparte na **Jinja2** — szablony per framework testowy
(pytest, JUnit, NUnit, Mocha, Jest oraz frameworki E2E — patrz
[ADR-007](./ADR-007-e2e-frameworks.md)). Szablony przyjmują zmienne z analizy
AST (nazwa funkcji, parametry, typ zwracany) i emitują gotowy do uruchomienia
kod. Rejestr szablonów pozwala dodawać nowe frameworki bez zmian w rdzeniu
generacji.

## Konsekwencje

**Pozytywne:**

- Spójny styl kodu i gotowe-do-uruchomienia testy.
- Łatwe dodawanie nowych frameworków (nowy szablon + rejestracja).
- Szablony dostosowywalne do konwencji projektu.

**Negatywne:**

- Koszt utrzymania szablonów przy zmianach frameworków.
- Ewolucja szablonów wymaga wersjonowania i testów regresyjnych (golden data).

## Powiązane

- [ADR-005](./ADR-005-tree-sitter-parser.md) — AST dostarcza zmiennych do szablonów.
- [ADR-008](./ADR-008-golden-data.md) — golden data waliduje stabilność szablonów.
- [ai/test-code-generation.md](../../ai-modules/analiza-kodu/test-code-generation.md) — opis generowania
  kodu per framework.
