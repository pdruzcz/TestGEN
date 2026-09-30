# Generowanie kodu testowego per framework (Epic 1)

Zamiana scenariusza testowego na gotowy do uruchomienia kod w wybranym
frameworku. Silnik szablonów: Jinja2 ([ADR-006](../../architecture/adr/ADR-006-jinja2-template-engine.md)).

## Frameworki jednostkowe/integracyjne

| Framework | Język | Typ |
|-----------|-------|-----|
| pytest | Python | unit |
| JUnit | Java | unit |
| NUnit | C# | unit |
| Mocha | JavaScript | unit |
| Jest | JavaScript/TypeScript | unit |

## Frameworki E2E/mobilne ([ADR-007](../../architecture/adr/ADR-007-e2e-frameworks.md))

| Framework | Zakres |
|-----------|--------|
| Selenium | automatyzacja webowa (wiele przeglądarek) |
| Playwright | web async/await z auto-waiting |
| Appium | mobilne (iOS/Android) |

Wspólny model specyfikacji (kroki `action`/`selector`/`value` + asercje)
mapowany na kod danego frameworka.

## Rejestr frameworków

Dodanie nowego frameworka:

1. Utwórz szablon Jinja2 w katalogu szablonów testowych.
2. Zarejestruj go w rejestrze frameworków.
3. Dodaj próbki golden data i testy regresyjne
   ([ADR-008](../../architecture/adr/ADR-008-golden-data.md)).

Szczegóły workflow: [workflows.md](../../architecture/workflows.md).

## Właściwości

- **Spójność** — ten sam styl kodu i importów niezależnie od autora scenariusza.
- **Gotowość do uruchomienia** — wygenerowany test działa bez ręcznych poprawek
  (po akceptacji w przeglądzie).
- **Utrwalenie** — kod zapisany w polu `test_code` przypadku testowego.

## Powiązane

- [ADR-006](../../architecture/adr/ADR-006-jinja2-template-engine.md), [ADR-007](../../architecture/adr/ADR-007-e2e-frameworks.md).
- [test-case-generation-native.md](./test-case-generation-native.md) — źródło
  scenariuszy.
