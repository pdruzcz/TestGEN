# ADR-005: tree-sitter jako parser AST

## Status

Accepted

## Kontekst

Platforma analizuje kod źródłowy w wielu językach o różnej jakości i
dokumentacji. Potrzebne jest precyzyjne, deterministyczne i wielojęzyczne
wykrywanie struktury (funkcje, klasy, importy, parametry) jako podłoże dla
generowania przypadków testowych. Parsowanie oparte na wyrażeniach regularnych
jest kruche; rozwiązania per-język mnożą koszty utrzymania.

## Decyzja

Wykorzystać **tree-sitter** (biblioteka C z wiązaniami Python) jako jedyny
parser AST, z per-language grammar. Obsługiwane języki: Python, Java, C#, C/C++,
JavaScript, TypeScript, Go. Wynik analizy (`logic_structures`) — funkcje, klasy,
importy, parametry, typy zwracane — utrwalany w `AnalysisResult.result_data`.

## Konsekwencje

**Pozytywne:**

- Precyzyjne, deterministyczne i powtarzalne wykrywanie struktury — te same
  wyniki między uruchomieniami.
- Wysoka wydajność (parser C) i szerokie wsparcie języków.
- Jednolity model ekstrakcji dla wszystkich języków.

**Negatywne:**

- Wymaga grammar per język; dodanie nowego języka to praca integracyjna.
- Inkrementalne aktualizacje grammar zależą od upstream tree-sitter.
- Wykrywanie semantyki wykraczające poza składnię wymaga warstwy reguł powyżej AST.

## Powiązane

- [ADR-006](./ADR-006-jinja2-template-engine.md) — generowanie kodu testowego na
  podstawie struktur z AST.
- [ai/ast-analysis.md](../../ai-modules/analiza-kodu/ast-analysis.md) — opis analizy AST.
