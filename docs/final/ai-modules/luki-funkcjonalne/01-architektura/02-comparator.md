# Comparator — fuzzy matching wymagań z kodem

> Plik: `backend/app/services/gap_analysis/comparator.py`

## 1. Odpowiedzialność

`ComparatorService` przyjmuje listę wymagań (`RequirementData`) i listę bytów
kodowych (`CodeEntity`) i dla każdej pary oblicza stopień podobieństwa.
Wynik przekazuje do `GapClassifier`, który podejmuje decyzję o typie luki.

## 2. Algorytmy dopasowania

Trzy komplementarne algorytmy czysto-Pythonowe (bez zewnętrznych zależności):
scikit-learn / jellyfish / thefuzz są celowo niewykorzystywane — dla projektów o
wielkości dziesiątek do niskich setek wymagań wydajność czystego Pythona jest
wystarczająca, a binary deps pozostają minimalne.

### 2.1 Levenshtein (edytowanie odległości)

`_levenshtein_match(req_name, code_name)` — odległość edycyjna znormalizowana do
[0.0, 100.0]:

```
score = (1 - dist / max_len) * 100
```

Klasyczny algorytm DP (m×n), ~25 linii. Dobra detekcja literówek i drobnych
zmian nazewnictwa (`getUserData` ↔ `get_user_data`).

### 2.2 Jaro-Winkler

`_jaro_winkler_match(req_name, code_name)` — Jaro similarity z premią dla
wspólnego prefiksu (Winkler). ~30 linii. Preferowany dla nazw z melodijnym
prefiksem (`authenticate` ↔ `authn`).

Wzór:

```
J = (1/3) * (m/|s1| + m/|s2| + (m-t)/m)        # Jaro
JW = J + l * p * (1 - J)                          # Winkler, l ≤ 4, p = 0.1
```

### 2.3 TF-IDF + cosine similarity

`_tfidf_cosine_match(req_text, code_text)` — semantyczne podobieństwo tekstu
wymagania i nazwy + docstring bytu. Implementacja oparta na `collections.Counter`
(TF) i IDF obliczanym w locie. ~40 linii.

Kroki:
1. Tokenizacja (lowercase + regex `\w+`)
2. Oblicz TF dla obu tekstów
3. IDF dla korpusu = oba teksty
4. Wektory TF-IDF
5. Cosine similarity

## 3. Kombinacja wyników

`_combine_scores(lev, jw, sem) -> float` — ważona średnia:

```
combined = lev * 0.25 + jw * 0.35 + sem * 0.40
```

Rationale wag:
- **Levenshtein 0.25** — najsłabszy dla różnic językowych, ale dobry na literówki.
- **Jaro-Winkler 0.35** — lepszy dla nazw funkcji (prefiksy).
- **Semantic TF-IDF 0.40** — najważniejszy; wykorzystuje pełny tekst wymagania
  i docstring.

Wagi są w stałej `_WEIGHTS` i mogą być strojone bez zmiany algorytmów.

## 4. Progi klasyfikacji

Po obliczeniu `combined` dla każdej pary, Comparator wybiera najlepsze
dopasowanie per wymaganie i przekazuje do klasyfikatora:

| Wynik combined | Klasyfikacja |
|---|---|
| `< 30.0` | brak dopasowania → `missing` |
| `30.0 – 70.0` | częściowe dopasowanie → `different` |
| `≥ 70.0` | dobre dopasowanie → wymaganie zaimplementowane (nie jest luką) |

Progi są w `classification_rules.py`:
- `MISSING_THRESHOLD = 30.0`
- `DIVERGENT_THRESHOLD = 70.0`
- `GOOD_MATCH_THRESHOLD = 70.0`

## 5. Struktury danych

### `RequirementData`
```python
@dataclass
class RequirementData:
    req_id: str
    text: str
    category: str = ""
    priority: str = "medium"   # low | medium | high | critical
```

### `CodeEntity` (z `services/analysis/gap_analyzer.py`)
```python
@dataclass
class CodeEntity:
    entity_id: str
    name: str
    type: str          # function | method | class | ...
    file_path: str
    line_number: int
    language: str      # python | typescript | java | csharp
    docstring: str | None = None
```

### `GapFindingData`
Wynik Comparator+Classifier. Pola: `requirement_id`, `code_entity_id`,
`gap_type`, `description`, `requirement_text`, `code_reference`, `match_score`,
`match_method`, `context`, `severity`.

## 6. API

```python
service = ComparatorService()
findings, summary = service.compare(requirements, code_entities)
# findings: list[GapFindingData]
# summary:  GapAnalysisSummaryData
```

## 7. Testowanie

Testy jednostkowe: `backend/tests/unit/services/gap_analysis/test_comparator.py`.
Golden testy (12 par kod+dokumentacja, 4 języki):
`backend/tests/golden_data/gap_analysis/*.json` + runner
`backend/tests/golden/test_gap_analysis_golden.py`.

AC golden:
- Recall ≥ 75% (per-case i średnia)
- Compliance accuracy ≥ 80% (missing count ±1)

## 8. Powiązane dokumenty

- [03 — Klasyfikator luk](03-klasyfikator-luk.md)
