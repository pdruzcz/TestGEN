# Agregator wyników i risk engine

Pliki: `finding_aggregator.py`, `risk_engine.py`, `cvss_calculator.py`

## CZĘŚĆ A — FindingAggregator

### 1. Cel
Konsoliduje znaleziska ze wszystkich skanerów: deduplikuje, koreluje i wylicza
spójny wskaźnik zaufania (confidence).

### 2. Interfejs
```python
async def aggregate(project_id, scan_ids, db) -> AggregationResult
def aggregate_findings(findings) -> AggregationResult
```
`AggregationResult` — `findings`, `summary`, `correlations`, `dedup_count`.

### 3. Deduplikacja
Klucz: `(file_path, line_start, vulnerability_type, cwe_id)`. Zachowuje
pierwsze wystąpienie, scala duplikaty (wyższy confidence, dziedziczenie
`taint_path`/`recommendation`), śledzi wszystkie `ScanType` per klucz.

### 4. Korelacja
Dopasowanie SAST↔DAST/TAINT po równości CWE lub nakładaniu się
`vulnerability_type` (np. „sql_injection” w „SQL Injection at…”).
`Correlation` — `sast_finding_id`, `dast_finding_id`, `correlation_type`
∈ {sast_dast, sast_taint}, `confidence_boost`.

### 5. Scoring zaufania
Bazowa pewność narzędzia:

| Narzędzie | Confidence bazowy |
|---|---|
| DEPENDENCY | 0.90 |
| DAST | 0.85 |
| TAINT | 0.80 |
| CONFIG | 0.75 |
| SAST | 0.70 |

- Boost za liczbę źródeł: `min(max(n-1,0),3) * 0.05` (maks. +0.15).
- Boost korelacji: **+0.20** SAST↔DAST, **+0.10** SAST↔TAINT (cap 0.20).
- Wynik: `min(base + source_boost + correlation_boost, 1.0)`.

Sortowanie: severity DESC, confidence DESC. Summary:
`{total_findings, severity_counts, source_counts}`.

## CZĘŚĆ B — RiskEngine

### 1. Cel
CVSS scoring, eskalacja severity, szacowanie wysiłku naprawy i priorytetyzacja.

### 2. Interfejs
```python
async def calculate_risk(project_id, db) -> RiskAssessment
def assess(findings) -> RiskAssessment
```
`RiskAssessment` — `prioritized_findings`, `cvss_distribution`, `top_10`,
`effort_estimates`.

### 3. Algorytm
1. Brak CVSS → wyprowadź z CWE (`cvss_calculator.default_vector_for`).
2. Brak OWASP → mapuj z CWE (`_OWASP_BY_CWE`).
3. Oszacuj effort z CWE (`_EFFORT_BY_CWE`): low (sanityzacja/update), medium
   (refaktor), high (przeprojektowanie auth).
4. Reguły eskalacji (bump +1 poziom severity):
   - SAST + DAST razem i severity ≠ CRITICAL → „Potwierdzona dynamicznie”.
   - DEPENDENCY z CVSS ≥ 9.0 i severity ≠ CRITICAL → „Zależność z publicznym
     exploitem”.
5. Wyrównaj severity z pasmem CVSS (bierze wyższe).
6. Sortuj `(-severity, -confidence, effort, -cvss)` → przypisz `priority`
   (1 = najwyższy).

### 4. Mapowanie CWE → effort
- **low:** CWE-89, 79, 352, 22, 798, 259, 1104, 611
- **medium:** CWE-78, 94, 502, 668, 918, 200
- **high:** CWE-639, 862

## CZĘŚĆ C — CVSSCalculator

Czysty kalkulator CVSS v3.1 (`cvss_calculator.py`). `CVSSVector` koduje 8
metryk bazowych (AV, AC, PR, UI, S, C, I, A). `calculate_cvss_base_score`
implementuje ISS, Impact, Exploitability i zaokrąglanie wg specyfikacji FIRST.
`default_vector_for(cwe, severity)` zwraca kanoniczne wektory NVD, np.:

| CWE | Wektor | Wynik |
|---|---|---|
| CWE-89 (SQLi) | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H | 9.8 |
| CWE-79 (XSS) | AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N | 6.1 |
| CWE-352 (CSRF) | AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N | 6.5 |

Referencja: FIRST CVSS v3.1 Specification.
