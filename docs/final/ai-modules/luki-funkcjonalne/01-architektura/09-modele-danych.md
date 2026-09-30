# Modele danych (ERD)

> Pliki: `backend/app/models/gap_finding.py`, `code_error.py`,
> `recommendation.py`, `compliance_snapshot.py`, `integration.py`

## 1. Diagram

```
┌─────────────┐         ┌──────────────────────┐
│  projects   │ 1───∞   │   gap_findings       │
│             │◄────────│   (gap analysis)     │
└──────┬──────┘         └──────────┬───────────┘
       │                           │ 1───∞
       │                           ▼
       │                ┌──────────────────────┐
       │                │   code_errors        │
       │                │   (detekcja błędów)  │
       │                └──────────────────────┘
       │
       │ 1───∞          ┌──────────────────────┐
       ├───────────────►│   recommendations    │
       │                │   (rekomendacje)     │
       │                └──────────┬───────────┘
       │                           │ ∞───1 (FK gap_finding)
       │                           ▼
       │                ┌──────────────────────┐
       │ 1───∞          │ compliance_snapshots │
       ├───────────────►│   (versioning)       │
       │                └──────────────────────┘
       │
       │ 1───∞          ┌──────────────────────┐
       └───────────────►│ integration_configs  │
                        │   (Jira / ADO)       │
                        └──────────┬───────────┘
                                   │ 1───∞
                                   ▼
                        ┌──────────────────────┐
                        │ integration_sync_logs│
                        └──────────────────────┘
```

## 2. gap_findings

Główna tabela modułu. Persystuje wszystkie znaleziska luk.

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID (PK) | Klucz główny |
| tenant_id | UUID | RLS tenant |
| project_id | UUID FK | Projekt |
| analysis_id | UUID FK nullable | Powiązany AnalysisResult |
| requirement_id | str nullable | ID wymagania (np. REQ-ANL-004) |
| code_entity_id | str nullable | ID bytu kodu (z AnalysisResult) |
| gap_type | Enum | missing, different, extra, inconsistent |
| description | Text | Opis luki |
| requirement_text | Text nullable | Treść wymagania |
| code_reference | str(500) nullable | file:line |
| match_score | Float | 0–100 |
| match_method | str(30) | lev, jw, sem, combined |
| context | JSONB | excerpt + alternatywne dopasowania |
| severity | str(10) | info, warning, critical |
| source | str(10) | pochodzenie znaleziska (Story 5.10) |
| skeleton_path | str(500) nullable | Path do skeleton (Story 5.6) |
| created_at, updated_at | DateTime | Timestamps |

**Indeksy**: project_id, gap_type, match_score, analysis_id, severity, source
**RLS**: tenant_id

## 3. code_errors

Błędy kodu wykryte przez detektory (Story 5.4).

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID PK | |
| project_id, tenant_id | UUID | RLS + scope |
| code_entity_id | str | Powiązany byt |
| file_path, line_start, line_end | str, int, int | Lokalizacja |
| error_category | Enum | syntax, logic, semantic, conformance |
| error_message | Text | Komunikat |
| severity | str(10) | info, warning, critical |
| suggested_fix | Text nullable | Sugerowana naprawa |
| context | JSONB | Ast / token info |

## 4. recommendations

Rekomendacje naprawcze (Story 5.5).

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID PK | |
| project_id, tenant_id | UUID | RLS + scope |
| gap_finding_id | UUID FK | Powiązana luka |
| priority | str(3) | P1, P2, P3, P4 |
| confidence | Float | 0.0–1.0 |
| suggested_action | Text | Konkretna akcja |
| effort_estimate | str(2) | S, M, L |
| source | str(10) | pochodzenie rekomendacji |
| status | str(10) | open, accepted, applied, dismissed |

## 5. compliance_snapshots

Punkt w czasie compliance (Story 5.7) — służy do porównań wersji.

| Kolumna | Typ | Opis |
|---|---|---|
| id | UUID PK | |
| project_id, tenant_id | UUID | RLS + scope |
| snapshot_date | DateTime | Moment snapshotu |
| project_score | Float | Compliance score 0–100 |
| module_scores | JSONB | {file_path: score} |
| finding_counts | JSONB | {missing: N, different: N, ...} |
| analysis_id | UUID FK nullable | Powiązany AnalysisResult |

## 6. integration_configs + integration_sync_logs

Konfiguracja i logi sync do Jira/Azure DevOps (Stories 5.8/5.9). Szczegóły w
[08 — Integracje](08-integracje.md).

## 7. Migracje

| Migracja | Story | Zakres |
|---|---|---|
| `022_add_gap_findings_table.py` | 5.1 | Tabela gap_findings + RLS |
| `023_add_code_errors_table.py` | 5.4 | Tabela code_errors |
| `024_add_recommendations_table.py` | 5.5 | Tabela recommendations |
| `025_add_skeleton_path_to_gap_findings.py` | 5.6 | Kolumna skeleton_path |
| `026_add_compliance_snapshots_table.py` | 5.7 | Tabela compliance_snapshots |
| `027_add_integration_tables.py` | 5.8/5.9 | integration_configs + sync_logs |
| `035_add_source_to_gap_findings.py` | 5.10 | Kolumna source |

## 8. RLS

Wszystkie tabele dziedziczą `TenantMixin` — wymusza `tenant_id` w zapytaniach
przez PostgreSQL Row-Level Security. Polityki RLS są dodawane w migracjach
per-tabela (wzorzec Epic 4).

## 9. Powiązane dokumenty

- [01 — Przegląd](01-overview.md)
- [08 — Integracje](08-integracje.md)
