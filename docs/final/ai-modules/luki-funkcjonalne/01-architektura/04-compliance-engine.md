# Compliance engine

> Plik: `backend/app/services/gap_analysis/compliance_engine.py`

## 1. Odpowiedzialność

`ComplianceEngine` oblicza zgodność implementacji z dokumentacją w skali 0–100,
gdzie 100 = pełna zgodność (brak luk), 0 = maksymalna niezgodność.

Obliczenie jest **w locie** (compute-on-the-fly) z rekordów `gap_findings` — bez
persystencji per finding. Snapshoty dla porównań wersji są persystowane osobno
w `compliance_snapshots` (patrz [Story 5.7](#)).

## 2. Poziomy scoringu

| Poziom | Funkcja | Grupowanie |
|---|---|---|
| Projekt | `calculate_project_score(findings)` | Globalnie |
| Moduł | `calculate_module_scores(findings)` | Per `file_path` |
| Funkcja | `calculate_function_scores(findings)` | Per `code_entity_id` |

## 3. Wzór scoringu

Dla zbioru findings w danej grupie:

```
score = max(0.0, 100.0 - Σ penalty(f) for f in findings)
```

Penalty zależy od kombinacji gap_type i severity (`PENALTY_WEIGHTS`):

| gap_type \ severity | critical | warning | info |
|---|---:|---:|---:|
| missing | 15 | 8 | 3 |
| different | 10 | 5 | 2 |
| inconsistent | 10 | 5 | 2 |
| extra | 5 | 3 | 1 |

Rationale:
- **Missing + critical** (15) — najdroższe; biznesowo ryzykowne.
- **Different + critical** (10) — częściowa implementacja krytycznego wymogu.
- **Inconsistent** (10/5/2) — sprzeczność wymagań; tyle samo co different.
- **Extra** (5/3/1) — kod poza zakresem dokumentacji; najmniej kosztowne.

Dolny limit 0 — żadna liczba luk nie zepchnie score poniżej zera.

## 4. Przykład

Projekt z 6 znaleziskami:
- 2× missing+critical = 2 × 15 = 30
- 1× missing+warning = 1 × 8 = 8
- 2× different+warning = 2 × 5 = 10
- 1× extra+info = 1 × 1 = 1

**Penalty łączny: 49 → score = 100 − 49 = 51.0**

## 5. Struktury wynikowe

```python
@dataclass
class ComplianceScore:
    score: float                       # 0–100
    total_findings: int
    breakdown: dict[str, int]          # {missing: 3, different: 2, ...}
    metadata: dict[str, Any]           # dodatkowe informacje

@dataclass
class ModuleScore:
    file_path: str
    score: float
    total_findings: int
    breakdown: dict[str, int]

@dataclass
class FunctionScore:
    code_entity_id: str
    score: float
    total_findings: int
    breakdown: dict[str, int]
    file_path: str | None
    entity_name: str | None
```

## 6. Endpointy API

- `GET /projects/{project_id}/compliance` — score projektu
- `GET /projects/{project_id}/compliance/modules` — lista score per moduł
- `GET /projects/{project_id}/compliance/functions` — lista score per funkcja
- `POST /projects/{project_id}/compliance/export` — CSV z wynikami

## 7. Eksport CSV

Eksport zawiera:
- wiersz nagłówka projektu
- wszystkie ModuleScores posortowane malejąco po liczbie findings
- wszystkie FunctionScores posortowane malejąco po liczbie findings

Format zgodny z Excel/LibreOffice (UTF-8 z separatorem przecinka).

## 8. Frontend

UI: `frontend/src/app/features/compliance/` — gauge wizualizujący score projektu,
tabela modułów z drill-down do funkcji, eksport do CSV. Dostępny z Project Detail
przyciskiem "Compliance".

## 9. Testowanie

Testy jednostkowe: `backend/tests/unit/services/gap_analysis/test_compliance_engine.py`.
Testy E2E: `backend/tests/integration/test_gap_analysis_routes.py`.

## 10. Powiązane dokumenty

- [03 — Klasyfikator luk](03-klasyfikator-luk.md)
- [01 — Przegląd](01-overview.md)
