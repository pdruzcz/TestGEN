# Klasyfikator 4 typów luk

> Plik: `backend/app/services/gap_analysis/classifier.py` + `classification_rules.py`

## 1. Odpowiedzialność

`GapClassifier` bierze wynik dopasowania z `ComparatorService` i dla każdego
wymagania produkuje ustrukturyzowane `GapFindingData` z:

- **gap_type** — jeden z 4 typów: `missing`, `different`, `extra`, `inconsistent`
- **severity** — `info` | `warning` | `critical`
- **context** — excerpt wymagania + excerpt bytu kodu (file/line)
- **description** — opis czytelny dla człowieka

## 2. Cztery typy luk

### 2.1 `missing` — brak implementacji

Wymaganie istnieje w dokumentacji, ale kod nie zawiera odpowiadającego bytu
(lub score < `MISSING_THRESHOLD` = 30.0).

Przykład: wymagane "System must export to PDF", w kodzie brak jakiegokolwiek
bytu o nazwie lub docstringu z "export"/"pdf".

**Severity**: zależna od priorytetu wymagań (patrz §4).

### 2.2 `different` — implementacja rozbieżna

Wymaganie jest częściowo zaimplementowane (score 30–70). Nazwa/docstring
wskazują na pokrewieństwo, ale nie ma pewności, że kod spełnia wymaganie w pełni.

Przykład: wymaganie "must retry failed tasks with exponential backoff", kod ma
`retryFailedTask()` ale bez widocznego mechanizmu backoff.

**Severity**: `warning` (domyślnie).

### 2.3 `extra` — kod bez wymagania

Byt kodu nie jest mapowany do żadnego wymagania. Traktowany jako potencjalny
dead code lub implementacja poza zakresem.

Wykluczenia (regex `EXCLUDE_PATTERNS`): `test_*`, `__init__`, `conftest`,
`setup`, `teardown`, `main`, `pytest_*`, `setUp`, `tearDown`, `before`, `after`.

Dodatkowo pomijane drobne akcesory (regex `MINOR_ENTITY_PATTERNS`): `get_*`,
`set_*`, `is_*`, `has_*`, `can_*` — te zazwyczaj są pomocnicze, nie stanowią
luky.

**Severity**: `info`.

### 2.4 `inconsistent` — sprzeczność między wymaganiami

Ten sam byt kodu jest najlepszym dopasowaniem dla 2+ wymagań, ale sygnały są
sprzeczne. Detekcja oparta na:

1. **Score spread** > `INCONSISTENT_SCORE_SPREAD` = 40.0 — duże różnice w
   dopasowaniu między wymaganiami wskazują, że kod częściowo spełnia jedno,
   a ignoruje drugie.
2. **Contradiction indicators** — pary słów (`must` ↔ `must not`, `allow` ↔
   `deny`, `enable` ↔ `disable`, `accept` ↔ `reject`, `include` ↔ `exclude`,
   `always` ↔ `never`, `required` ↔ `optional`) w wymaganiach mapowanych do
   tego samego bytu.

**Severity**: `critical` (zawsze).

## 3. Reguły klasyfikacji

```python
# Pseudokod GapClassifier.classify()
for mapping in mappings:
    if mapping.best_score < MISSING_THRESHOLD:        # < 30
        classify_missing(mapping)
    elif mapping.best_score < DIVERGENT_THRESHOLD:    # 30-70
        classify_different(mapping)
    # else: ≥ 70 — dopasowane, nie jest luką

# Phase 3: detekcja inconsistent (cross-requirement)
for entity, req_ids in detect_inconsistent(mappings, all_scores):
    upgrade_or_create_inconsistent_findings(entity, req_ids)

# Phase 4: extra = byty kodu bez mapowania (po wykluczeniach)
for entity in code_entities:
    if entity.id not in matched_entity_ids and not is_excluded(entity):
        classify_extra(entity)
```

## 4. Mapowanie severity

Domyślne severity per gap_type (`SEVERITY_MAP`):

| gap_type | severity |
|---|---|
| missing | warning |
| different | warning |
| extra | info |
| inconsistent | critical |

Wyjątek dla `missing`: nadpisane przez priorytet wymagania (`PRIORITY_SEVERITY`):

| priority | severity |
|---|---|
| high / critical | critical |
| medium / low | warning |

Rationale: brak implementacji wymagań high-priority to ryzyko biznesowe, więc
musi być traktowane jako critical.

## 5. Context excerpts

Każde finding zawiera `context` (JSONB) z:

- `requirement_excerpt` — pełny tekst wymagania
- `code_excerpt` — nazwa + docstring + file:line bytu
- `match_scores` — szczegółowe wyniki per algorytm (lev/jw/sem/combined)
- `alternative_matches` — kolejne 2 najlepsze kandydaty (jeśli > 1)

## 6. Konfiguracja

Wszystkie progi i reguły wydzielone do `classification_rules.py`:

```python
MISSING_THRESHOLD = 30.0
DIVERGENT_THRESHOLD = 70.0
GOOD_MATCH_THRESHOLD = 70.0
INCONSISTENT_SCORE_SPREAD = 40.0

EXCLUDE_PATTERNS = re.compile(r"^(test_|__|conftest|...)$")
MINOR_ENTITY_PATTERNS = re.compile(r"^(get_|set_|is_|...)$")

SEVERITY_MAP = {"missing": "warning", "different": "warning", "extra": "info", "inconsistent": "critical"}
PRIORITY_SEVERITY = {"high": "critical", "medium": "warning", "low": "warning"}

CONTRADICTION_INDICATORS = [("must", "must not"), ("allow", "deny"), ...]
```

## 7. Testowanie

Testy jednostkowe: `backend/tests/unit/services/gap_analysis/test_classifier.py`
pokrywają wszystkie 4 typy, wykluczenia, priority severity upgrade, inconsistent
detekcję.

## 8. Powiązane dokumenty

- [02 — Comparator](02-comparator.md)
- [04 — Compliance engine](04-compliance-engine.md)
