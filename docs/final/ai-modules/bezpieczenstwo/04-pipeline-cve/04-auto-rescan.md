# Pipeline CVE — auto re-skan projektów i powiadomienia

## 1. Wykrywanie dotkniętych projektów

```python
async def _find_affected_projects(records, db) -> list[AffectedProject]
```

Po zapisaniu nowych CVE pipeline porównuje je z zależnościami projektów i
buduje listę `AffectedProject` (`project_id`, `project_name`, `owner_id`,
`affected_packages`, `new_cves`).

## 2. Wyzwolenie re-skanu

```python
def _trigger_dependency_rescan(project_ids) -> None
```

Wywołuje zadanie Celery `rescan_affected_projects.delay(project_ids)`.

`rescan_affected_projects(project_ids)` (`cve_tasks.py`):
- Tworzy rekordy `SecurityScan` z `ScanType.DEPENDENCY`.
- Dyspozytuje `run_dependency_scan.delay()` per projekt.

Dzięki temu projekty z nowo dotkniętymi pakietami są automatycznie ponownie
skanowane bez udziału użytkownika.

## 3. Powiadomienia

```python
async def _send_notifications(affected, db) -> None
```

Loguje ustrukturyzowane powiadomienie (haki e-mail jako placeholder) dla
właścicieli dotkniętych projektów.

## 4. Przepływ end-to-end

```
update_cve_database (cron 1. dnia, 02:00 UTC)
  → fetch NVD/OSV/GitHub
  → merge + deduplicate
  → save_to_database
  → find_affected_projects
  → trigger_dependency_rescan (Celery)
        → SecurityScan(DEPENDENCY) + run_dependency_scan
  → send_notifications
  → CVEUpdateResult (total_new, total_updated, affected_projects, errors)
```

## 5. Logowanie przebiegu

Każdy przebieg zapisuje `CVEUpdateLog` (running → completed/failed) oraz
`SourceStatus` per źródło, co umożliwia audyt i diagnozę niepowodzeń pobierania.
