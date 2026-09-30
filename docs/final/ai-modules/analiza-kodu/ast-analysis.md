# Analiza AST kodu źródłowego (Epic 1)

Deterministyczna analiza struktury kodu na podstawie drzewa składniowego.
Podłoże dla generowania przypadków testowych i analizy regresji. Parser:
tree-sitter ([ADR-005](../../architecture/adr/ADR-005-tree-sitter-parser.md)).

## Obsługiwane języki

Python, Java, C#, C/C++, JavaScript, TypeScript, Go. Wybór grammar per język;
język wykrywany automatycznie z rozszerzenia/zawartości (można wymusić).

## Ekstrahowane struktury (`logic_structures`)

Analiza produces ustrukturyzowany opis jednostki kodu, utrwalany w
`AnalysisResult.result_data` (JSONB):

| Element | Pola |
|---------|------|
| **Funkcja** | `name`, `file_path`, `line_start`/`line_end`, `parameters` (nazwa + typ), `return_type`, modyfikatory |
| **Klasa** | `name`, `file_path`, metody, atrybuty, dziedziczenie, modyfikatory dostępu |
| **Import** | moduł, alias, importowane nazwy |
| **Wywołanie** | nazwa, argumenty (statycznie rozwiązywalne) |

Przykład:

```json
{
  "functions": [{
    "name": "calculate_total", "file_path": "app/cart.py",
    "line_start": 15, "line_end": 25,
    "parameters": [{"name": "items", "type": "list"}, {"name": "tax_rate", "type": "float"}],
    "return_type": "float"
  }]
}
```

## Właściwości

- **Determinizm** — te same wejście daje te same wyjście między uruchomieniami.
- **Wydajność** — parser C (tree-sitter), analiza inkrementalna możliwa dla
  dużych baz kodu.
- **Dokładność strukturalna** — pełna ścieżka pliku, zakresy linii, sygnatury.

## Buforowanie i diff

- **Buforowanie** — wyniki analizy buforowane; ponowna analiza niezmienionych
  plików korzysta z cache.
- **Diff analizy** — porównanie dwóch wersji analizy wykrywa dodane/usunięte/
  zmienione struktury → podłoże analizy regresji
  ([regression-analysis.md](./regression-analysis.md)).

## Powiązane

- [ADR-005](../../architecture/adr/ADR-005-tree-sitter-parser.md) — wybór parsera.
- [test-case-generation-native.md](./test-case-generation-native.md) — struktury
  zasilają generowanie przypadków testowych.
- [api/examples/analysis_examples.md](../../architecture/api/examples/analysis_examples.md) —
  endpointy analizy kodu.
