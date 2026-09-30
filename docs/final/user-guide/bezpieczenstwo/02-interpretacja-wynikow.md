# Przewodnik użytkownika — interpretacja wyników

## 1. Pola znaleziska (SecurityFinding)

| Pole | Znaczenie |
|---|---|
| `vulnerability_type` | typ podatności (np. sql_injection) |
| `severity` | CRITICAL / HIGH / MEDIUM / LOW / INFO |
| `cwe_id` | identyfikator CWE |
| `owasp_category` | kategoria OWASP Top 10 (2021) |
| `file_path` / `line_start` | lokalizacja |
| `confidence` | zaufanie 0.0–1.0 |
| `source` | silnik, który wykrył znalezisko |
| `cvss_score` / `cvss_vector` | ocena CVSS v3.1 |
| `priority` | priorytet naprawy (1 = najwyższy) |
| `status` | OPEN / ACKNOWLEDGED / FIXED / FALSE_POSITIVE |

## 2. Severity vs CVSS

Severity wyrównywane jest z pasmem CVSS (bierze wyższą wartość):

| CVSS | Severity |
|---|---|
| 9.0–10.0 | critical |
| 7.0–8.9 | high |
| 4.0–6.9 | medium |
| 0.1–3.9 | low |
| 0.0 | info |

## 3. Confidence — jak czytać

Confidence bazuje na narzędziu (DEPENDENCY 0.90 > DAST 0.85 > TAINT 0.80 >
CONFIG 0.75 > SAST 0.70), z premią za:
- wiele źródeł wykrywających to samo (+do 0.15),
- korelację SAST↔DAST (+0.20) lub SAST↔TAINT (+0.10).

Wysoki confidence + wiele źródeł = silny sygnał (mała szansa na false
positive).

## 4. Raport zagregowany

```
GET /projects/{project_id}/security-report
```

Zwraca zdeduplikowane, skorelowane znaleziska + `dedup_count` i
`correlation_count`.

## 5. Dashboard

```
GET /projects/{project_id}/security-dashboard
```

Zawiera rozkład CVSS, top 10 znalezisk i sekwencję napraw — patrz
[priorytetyzacja](03-priorytetyzacja-napraw.md).

## 6. Filtrowanie znalezisk

```
GET /projects/{project_id}/security-findings?severity=HIGH&scan_type=SAST&cwe_id=CWE-89
```

Filtry: `scan_id`, `severity`, `scan_type`, `status`, `vulnerability_type`,
`file_path`, `cwe_id`, `page`, `page_size`.
