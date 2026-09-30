# Pipeline CVE — harmonogram i konfiguracja

## 1. Harmonogram (Celery Beat)

Wpis w `celery_app.py`:

```python
"cve-update-database-monthly": {
    "task": "security.update_cve_database",
    "schedule": crontab(hour=2, minute=0, day_of_month=1),
    "options": {"queue": "security"},
}
```

- Uruchomienie: **02:00 UTC, 1. dnia każdego miesiąca**.
- Nazwa zadania: `security.update_cve_database`.
- Kolejka: `security`.

## 2. Konfiguracja zadania (`cve_tasks.py`)

`update_cve_database()`:

| Parametr | Wartość |
|---|---|
| Max retries | 3 |
| Hard time limit | 3600 s (1 h) |
| Soft time limit | 3300 s (55 min) |
| Retry backoff | 10 s, 60 s, 300 s |

Zadanie zapisuje `CVEUpdateLog` ze statusem (running → completed/failed).

## 3. Rate limiting

- NVD: opcjonalny `nvd_api_key` (podnosi limit zapytań).
- GitHub: `github_token` (bearer).
- Paginacja NVD: `resultsPerPage=2000` + `startIndex`.

Pobieranie z trzech źródeł równoległe, ale każde źródło respektuje własne
limity API; błędy źródła są raportowane w `SourceStatus` i nie przerywają
całego przebiegu.

## 4. Orkiestracja głównego przebiegu

```python
async def update_cve_database(db) -> CVEUpdateResult
```

Kroki: fetch (NVD/OSV/GitHub równolegle) → merge & deduplicate → persist →
znajdź dotknięte projekty → wyzwól re-skany → wyślij powiadomienia.
Szczegóły re-skanu: [auto-rescan](04-auto-rescan.md).

## 5. Walidacja na danych golden

Auto-generowane reguły są walidowane na korpusie golden przed włączeniem —
patrz [auto-generowanie reguł](03-auto-generowanie-regul.md). Próg
fałszywych dopozytywów: `_MAX_FPR = 0.05` (5%).
