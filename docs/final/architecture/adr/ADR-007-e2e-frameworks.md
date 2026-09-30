# ADR-007: Wsparcie wieloframeworkowe dla testów E2E

## Status

Accepted

## Kontekst

Nowoczesne aplikacje webowe i mobilne wymagają testów E2E w różnych przeglądarkach
i na różnych platformach. Zespoły używają różnych narzędzi w zależności od
preferencji i stacku; ograniczenie się do jednego frameworka zawęża użyteczność
platformy. Sekwencje kroków (akcje, selektory, asercje) są jednak wspólne
niezależnie od narzędzia.

## Decyzja

Generatory kodu testowego dla trzech głównych frameworków E2E, zbudowane nad
silnikiem Jinja2 (ADR-006):

- **Selenium** — klasyczna automatyzacja webowa,
- **Playwright** — nowoczesne podejście async/await z auto-waiting,
- **Appium** — testowanie mobilne (iOS/Android).

Wspólny model specyfikacji testu (kroki `action`/`selector`/`value` + asercje)
mapowany na kod danego frameworka.

## Konsekwencje

**Pozytywne:**

- Użytkownik wybiera optymalne narzędzie dla swojego przypadku użycia.
- Wspólny generator testów regresyjnych działa dla wszystkich frameworków.
- Reuse modelu specyfikacji między frameworkami.

**Negatywne:**

- Większa ilość szablonów do utrzymania.
- Konieczność nadążania za aktualizacjami frameworków (Selenium/Playwright/Appium).

## Powiązane

- [ADR-006](./ADR-006-jinja2-template-engine.md) — silnik szablonów.
- [ai/test-code-generation.md](../../ai-modules/analiza-kodu/test-code-generation.md) — generowanie kodu
  E2E.
