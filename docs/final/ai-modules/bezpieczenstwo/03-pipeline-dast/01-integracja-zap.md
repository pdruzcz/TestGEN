# Pipeline DAST — integracja OWASP ZAP

Plik: `app/services/security_scan/dast_runner.py`

## 1. Architektura integracji

`DASTRunner` steruje instancją OWASP ZAP (obraz `owasp/zap2docker-stable`)
przez protokół `ZAPController` (Protocol), który abstrahuje kontener Docker i
REST API ZAP. Dzięki temu w testach można wstrzyknąć atrapę kontrolera bez
uruchamiania prawdziwego ZAP.

## 2. Cykl życia skanu

```
start kontenera → oczekiwanie na gotowość → (autentykacja) →
spider → active scan → polling statusu → pobranie alertów →
sanityzacja → mapowanie na SecurityFinding → zatrzymanie
```

## 3. Konfiguracja

| Parametr | Wartość domyślna | Znaczenie |
|---|---|---|
| `_DEFAULT_SCAN_TIMEOUT` | 1800 s (30 min) | maks. czas active scan |
| `_DEFAULT_READY_TIMEOUT` | 120 s (2 min) | oczekiwanie na start ZAP |

Gotowość sprawdzana przez polling endpointu
`/JSON/core/view/version/`.

## 4. Wywołanie

```python
async def run_dast(project_id, tenant_id, scan_id, target_url, auth_config) -> list[SecurityFinding]
```

`target_url` jest wymagany (walidacja na wejściu). `auth_config` opcjonalny —
patrz [autentykacja](03-autentykacja.md).

## 5. Endpoint API

Skan DAST uruchamiany asynchronicznie przez
`POST /projects/{project_id}/security-scan` z `scan_type=DAST`, `target_url`
i opcjonalnym `auth_config`. Dyspozytor wywołuje
`run_dast_scan.delay(scan_id, project_id, tenant_id, target_url, auth_config_dict)`.

## 6. Limity i bezpieczeństwo

- Skan tylko na autoryzowanych celach (target uruchomionej aplikacji
  projektu).
- Request/response w znaleziskach są sanityzowane (patrz
  [parsowanie wyników](04-parsowanie-wynikow.md)).
