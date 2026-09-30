# Skeleton generator

> Plik: `backend/app/services/gap_analysis/skeleton_generator.py`

## 1. Odpowiedzialność

`SkeletonGenerator` produkuje szkielet implementacji dla luk typu `missing` —
czyli tam, gdzie wymaganie istnieje, ale kod nie zawiera odpowiadającego bytu.

Szkielet to gotowy do wklejenia plik źródłowy z:
- poprawną składnią języka
- sygnaturą funkcji / klasy opartą na nazwie wymagania
- docstringiem / komentarzem TODO wskazującym powiązane wymaganie
- stub implementacji ( NotImplementedError / NotImplemented / zwracający null )

## 2. Obsługiwane języki

| Język | Rozszerzenie | Skeleton pattern |
|---|---|---|
| Python | `.py` | `def func(...): raise NotImplementedError(...)` |
| TypeScript | `.ts` | `function func(...): T { throw new Error("Not implemented"); }` |
| Java | `.java` | `public T func(...) { throw new UnsupportedOperationException(); }` |
| C# | `.cs` | `public T Func(...) { throw new NotImplementedException(); }` |

## 3. Mechanizm

1. **Walidacja wejścia** — finding musi być typu `missing`, musi mieć
   `requirement_id` i `requirement_text`.
2. **Konwersja nazwy wymagania na identyfikator** — `_normalize_identifier()`:
   - camelCase / snake_case w zależności od języka
   - usunięcie stop-słów ("System must", "shall")
   - dla Java/C#: PascalCase
3. **Render szablonu Jinja2** — `templates/{language}.j2`
4. **Walidacja składni** — tree-sitter parse na wyjściu
5. **Zwrócenie** `SkeletonResponse` z `code`, `language`, `file_name`, `skeleton_path`

## 4. Szablony Jinja2

Lokalizacja: `backend/app/services/gap_analysis/templates/`

Przykład (`python.j2`):

```python
"""TODO: {{ requirement_text }}

Requirement ID: {{ requirement_id }}
Priority: {{ priority }}
Generated from gap analysis — do not edit this header.
"""

def {{ function_name }}({{ params }}):
    """{{ requirement_text }}"""
    raise NotImplementedError(
        "Skeleton for {{ requirement_id }} — implement per spec."
    )
```

## 5. Walidacja tree-sitter

Po wyrenderowaniu szablonu, generator wywołuje tree-sitter aby upewnić się, że
wynik jest poprawnym kodem w danym języku. Błędy składni są rzadkie (szablony są
starannie sformułowane), ale walidacja daje gwarancję, że użytkownik dostaje
kompilowalny / interpretowalny kod.

## 6. Persystencja

Pole `gap_findings.skeleton_path` przechowuje ścieżkę do wygenerowanego pliku
skeletonu (migracja `025_add_skeleton_path_to_gap_findings.py`). Generator
zapisuje plik pod:

```
{project_root}/.testgen/skeletons/{requirement_id}.{ext}
```

## 7. Endpointy API

- `POST /projects/{project_id}/gap-findings/{finding_id}/skeleton` — generuje
  skeleton dla danej luki
- `GET /projects/{project_id}/gap-findings/{finding_id}/skeleton` — zwraca
  istniejący skeleton

## 8. Frontend

UI: przycisk "Generuj skeleton" w wierszu tabeli findings dla `gap_type=missing`.
Modal z podglądem kodu (CodeMirror / Monaco), przycisk "Kopiuj do schowka" +
"Pobierz plik".

## 9. Testowanie

Testy jednostkowe: `backend/tests/unit/services/gap_analysis/test_skeleton_generator.py`
— pokrywają 4 języki, normalizację nazw, walidację tree-sitter.

## 10. Powiązane dokumenty

- [05 — Recommendation engine](05-recommendation-engine.md)
- [03 — Klasyfikator luk](03-klasyfikator-luk.md)
