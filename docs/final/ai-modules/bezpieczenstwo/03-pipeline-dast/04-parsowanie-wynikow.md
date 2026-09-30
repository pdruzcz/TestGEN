# Pipeline DAST — parsowanie wyników

## 1. Od alertu ZAP do SecurityFinding

```
alerty ZAP (JSON) → _parse_zap_alerts → DASTFinding →
_sanitize_request_response → _to_finding → SecurityFinding
```

## 2. DASTFinding

Pola: `url`, `method`, `vulnerability_type`, `severity`, `cwe_id`,
`evidence` (fragment odpowiedzi), `plugin_id`, `request`, `response`
(sanityzowane), `recommendation`, `extra`.

## 3. Mapowanie severity

Ryzyko ZAP → `Severity`:

| Ryzyko ZAP | Severity |
|---|---|
| high | HIGH |
| medium | MEDIUM |
| low | LOW |
| informational / info | INFO |

`_map_zap_risk_to_severity()` realizuje to mapowanie.

## 4. Mapowanie CWE

`_map_zap_to_cwe(plugin_id, cweid)`:
1. Jeśli alert ma własny `cweid` — użyj go.
2. W przeciwnym razie fallback `_PLUGIN_TO_CWE` (np. 40018→CWE-89,
   40012→CWE-79, 90020→CWE-78).

## 5. Sanityzacja request/response

`_sanitize_request_response(request, response)`:

- Nagłówki wrażliwe → `[REDACTED]`: `authorization`, `cookie`, `set-cookie`,
  `x-api-key`, `x-auth-token`, `proxy-authorization`.
- `_TOKEN_RE` zastępuje wartości po `password`/`passwd`/`token`/`secret`/
  `api_key`/`access_token` → `[REDACTED]`.

Zapewnia to, że dane uwierzytelniające i tokeny nie trafiają do bazy znalezisk
ani raportów.

## 6. Korelacja z SAST

Znaleziska DAST są następnie korelowane ze znaleziskami SAST przez
`FindingAggregator` (boost +0.20 dla pary SAST↔DAST) — dynamiczne
potwierdzenie podatności statycznej podnosi zaufanie i może eskalować severity
w [risk engine](../01-architektura/07-agregator-i-risk-engine.md).
