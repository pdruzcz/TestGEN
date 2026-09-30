# DAST runner — dynamiczna analiza (OWASP ZAP)

Plik: `app/services/security_scan/dast_runner.py`
Klasa publiczna: `DASTRunner`

## 1. Cel

Orkiestruje cykl życia OWASP ZAP w celu dynamicznego testowania uruchomionej
aplikacji: start → gotowość → autentykacja → spider → active scan → alerty →
zatrzymanie. Patrz też [pipeline DAST](../03-pipeline-dast/01-integracja-zap.md).

## 2. Interfejs

```python
async def run_dast(project_id, tenant_id, scan_id, target_url, auth_config) -> list[SecurityFinding]
```

## 3. Struktury danych

- **AuthConfig** — `auth_type` ∈ {form, token, basic} + `credentials`
  (login_url, username_field, password_field, token, username, password).
  Fabryka `from_dict()` waliduje typ i ekstrahuje dane.
- **DASTFinding** — `url`, `method`, `vulnerability_type`, `severity`,
  `cwe_id`, `evidence`, `plugin_id`, `request`, `response`, `recommendation`,
  `extra`.
- **ZAPController** (Protocol) — wstrzykiwalny kontroler kontenera + REST API
  (umożliwia testy z atrapą).

## 4. Algorytm

1. Walidacja `target_url` (wymagany).
2. Start kontenera ZAP (lub wstrzyknięty mock).
3. Oczekiwanie na gotowość (polling `/JSON/core/view/version/`, limit 120 s).
4. Konfiguracja autentykacji (form/token/basic) przez ZAP Replacer API.
5. Spider (crawl) na `target_url`.
6. Active scan; polling statusu do 100% lub timeout (domyślnie 1800 s).
7. Pobranie alertów (JSON).
8. Sanityzacja request/response (poniżej).
9. Mapowanie alertów ZAP → `DASTFinding` → `SecurityFinding`.

## 5. Sanityzacja danych wrażliwych

- Nagłówki wrażliwe → `[REDACTED]`: `authorization`, `cookie`, `set-cookie`,
  `x-api-key`, `x-auth-token`, `proxy-authorization`.
- `_TOKEN_RE` zastępuje wartości po `password`/`token`/`api_key`/
  `access_token` → `[REDACTED]`.

## 6. Mapowanie ZAP → CWE

`_PLUGIN_TO_CWE` jako fallback gdy alert nie ma CWE, np.: 40018→CWE-89 (SQLi),
40012→CWE-79 (Reflected XSS), 90020→CWE-78 (OS Command Injection).
Ryzyko ZAP (high/medium/low/informational) → `Severity`.

## 7. Stałe

- `_DEFAULT_SCAN_TIMEOUT = 1800` (30 min).
- `_DEFAULT_READY_TIMEOUT = 120` (2 min).

## 8. Zależności

OWASP ZAP (`owasp/zap2docker-stable`), Docker SDK, `httpx`.
