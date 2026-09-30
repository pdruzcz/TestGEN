# Przewodnik użytkownika — uruchamianie skanu

## 1. Typy skanów

| scan_type | Co analizuje |
|---|---|
| SAST | kod źródłowy (reguły wzorców) |
| TAINT | przepływ danych source→sink |
| DEPENDENCY | zależności / CVE / SBOM |
| CONFIG | Docker / Kubernetes / Terraform |
| DAST | uruchomiona aplikacja (OWASP ZAP) |

## 2. Uruchomienie skanu (API)

```
POST /projects/{project_id}/security-scan
```

Body (`SecurityScanRequest`):

```json
{
  "scan_type": "SAST",
  "target_url": null,              // wymagany dla DAST
  "auth_config": null              // opcjonalny dla DAST
}
```

Odpowiedź: `202 Accepted` z `scan_id`, `task_id`, `status`. Skan działa
asynchronicznie (Celery) na deterministycznych silnikach — offline,
z powtarzalnymi wynikami.

## 3. Śledzenie statusu

```
GET /projects/{project_id}/security-scans              # lista skanów
GET /projects/{project_id}/security-scans/{scan_id}    # status + severity
```

Status przechodzi: PENDING → RUNNING → COMPLETED / FAILED.

## 4. Skan DAST — wymagania

DAST wymaga uruchomionej aplikacji pod `target_url`. Dla chronionych ścieżek
podaj `auth_config` (form/token/basic) — patrz
[autentykacja DAST](../../ai-modules/bezpieczenstwo/03-pipeline-dast/03-autentykacja.md).

## 5. SBOM (tylko DEPENDENCY)

```
GET /projects/{project_id}/security-scans/{scan_id}/sbom?sbom_format=cyclonedx
```

Format: `cyclonedx` lub `spdx`.

## 6. Dostęp z UI

Skany uruchamiasz i przeglądasz z poziomu widoku projektu (sekcja
bezpieczeństwo). Wyniki agregowane są w
[dashboardzie bezpieczeństwa](02-interpretacja-wynikow.md).
