# Modele danych — moduł bezpieczeństwa

Plik: `app/models/security_finding.py`

## 1. Enumy

- **ScanType:** SAST, TAINT, DEPENDENCY, CONFIG, DAST
- **Severity:** CRITICAL, HIGH, MEDIUM, LOW, INFO
- **AnalysisSource:** źródło wykrycia znaleziska
- **FindingStatus:** OPEN, ACKNOWLEDGED, FIXED, FALSE_POSITIVE
- **ScanStatus:** PENDING, RUNNING, COMPLETED, FAILED

## 2. Diagram ERD (uproszczony)

```
  ┌────────────────┐        ┌──────────────────┐
  │ SecurityScan   │ 1    n │ SecurityFinding  │
  │                │────────│                  │
  │ id (PK)        │        │ id (PK)          │
  │ tenant_id      │        │ scan_id (FK)     │
  │ project_id     │        │ tenant_id        │
  │ scan_type      │        │ project_id       │
  │ status         │        │ vulnerability... │
  │                │        │ severity / cwe   │
  │ findings_count │        │ confidence/source│
  │ scan_metadata  │        │ taint_path/poc   │
  └────────────────┘        └──────────────────┘

  ┌────────────────┐
  │ CVEDatabase    │  (publiczne dane referencyjne, NIE tenant-scoped)
  │ cve_id / pkg   │
  │ ecosystem      │
  │ cvss_score     │
  └────────────────┘
```

## 3. Tabela SecurityScan

| Kolumna | Typ | Uwagi |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | FK, index |
| project_id | UUID | FK, index |
| scan_type | Enum ScanType | index |
| status | Enum ScanStatus | default PENDING, index |
| task_id | str \| None | id zadania Celery |
| target_url | str \| None | 1000 znaków (DAST) |
| started_at / completed_at | DateTime | |
| findings_count | int | |
| error_message | text | |
| scan_metadata | JSONB | np. payload SBOM |
| created_at / updated_at | TimestampMixin | |

## 4. Tabela SecurityFinding

Kluczowe kolumny: `id` (PK), `tenant_id`, `project_id` (index), `scan_id`
(FK, index), `scan_type` (index), `vulnerability_type` (index), `severity`
(index), `cwe_id`, `owasp_category`, `file_path` (index), `line_start`,
`line_end`, `code_snippet` (text, przycinany do 500 zn.), `description`,
`confidence` (float 0–1), `source` (Enum AnalysisSource, default NATIVE),
`status` (Enum FindingStatus, default OPEN, index), `taint_path` (JSONB),
`recommendation`, `finding_metadata` (JSONB).

**Pola risk engine (Story 4.8):** `cvss_score`, `cvss_vector`, `priority`
(1 = najwyższy), `effort` (low/medium/high), `escalation_reason`.

**Pola PoC (Story 4.10):** `poc_payload`, `poc_steps` (JSONB),
`poc_expected_effect`.

## 5. Tabela CVEDatabase

Publiczne dane referencyjne (NIE tenant-scoped): `id` (PK), `cve_id` (index),
`package_name` (index), `ecosystem` (index), `cvss_score`, `severity`,
`description`, `affected_versions`, `fixed_version`, `published_date`,
`source_db` (default "osv", ∈ {nvd, osv, snyk}).
