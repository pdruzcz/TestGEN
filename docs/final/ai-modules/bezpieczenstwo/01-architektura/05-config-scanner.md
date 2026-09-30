# Config scanner — skaner konfiguracji infrastruktury

Plik orkiestratora: `app/services/security_scan/config_scanner.py`
Skanery technologiczne: `app/services/security_scan/config_scanners/`
Klasa publiczna: `ConfigScanner`

## 1. Cel

Wykrywa błędy konfiguracji (misconfigurations) w plikach Infrastructure-as-Code:
Docker, Kubernetes i Terraform. Orkiestrator klasyfikuje plik po nazwie i
kieruje go do właściwego skanera technologicznego.

## 2. Klasyfikacja plików

| Wzorzec nazwy | Technologia |
|---|---|
| `dockerfile*`, `docker-compose*.yml` | docker |
| `*.tf`, `*.tf.json` | terraform |
| `*.yaml`, `*.yml` (nie Docker/TF) | kubernetes |

## 3. Interfejs

```python
def scan_content(content: str, filename: str) -> list[ConfigFinding]
async def scan_config(project_id, tenant_id, scan_id) -> list[SecurityFinding]
```

`ConfigFinding` (`config_scanners/base.py`): `rule_id`, `config_type`,
`severity`, `description`, `recommendation`, `fix_example`, `file_path`,
`line`, `vulnerability_type`, `cwe_id`, `source`, `extra`.

Interfejs skanerów: `IConfigScanner` (Protocol) — właściwość `config_type` +
`scan(content, filename) -> list[ConfigFinding]`.

## 4. Reguły per technologia

### Docker (`docker_scanner.py`)
`LATEST_TAG` (CWE-1104, medium), `ROOT_USER` (CWE-250, high), `EXPOSED_PORT`
(CWE-668, medium — porty wrażliwe 22/23/3306/5432/6379/27017/9200/5984),
`HARDCODED_SECRET` (CWE-798, critical), `SUDO_IN_DOCKER` (CWE-250, high),
`NO_HEALTHCHECK` (CWE-754, low), `PRIVILEGED_CONTAINER` (compose, CWE-250,
critical).

### Kubernetes (`kubernetes_scanner.py`)
Analizuje workloady (Pod/Deployment/StatefulSet/DaemonSet/ReplicaSet/Job/
CronJob): `DEFAULT_NAMESPACE` (CWE-1188, low), `HOST_NETWORK` (CWE-668, high),
`PRIVILEGED_CONTAINER` (CWE-250, critical), `RUN_AS_ROOT` (CWE-250, high),
`NO_RESOURCE_LIMITS` (CWE-770, medium).

### Terraform (`terraform_scanner.py`)
Regex/HCL: `PUBLIC_S3_BUCKET` (CWE-732, high), `OPEN_SECURITY_GROUP` (CWE-284,
critical — `0.0.0.0/0`), `PLAINTEXT_SECRET` (CWE-312, medium), `NO_ENCRYPTION`
(CWE-311, high — dla `aws_s3_bucket`/`aws_db_instance`/`aws_ebs_volume`),
`NO_LOGGING` (CWE-778, medium).

## 5. Algorytm orkiestratora

1. Klasyfikuj plik → wybierz skaner.
2. Zbierz `ConfigFinding`.
3. Deduplikuj po `(file_path, line, rule_id)`.
4. Mapuj na `SecurityFinding`, kategoria OWASP =
   `A05:2021-Security Misconfiguration`. Confidence: 0.85.

## 6. Limity

- 1 MB na plik (`_MAX_CONTENT_BYTES = 1_000_000`).

Pełna lista reguł konfiguracji: ten plik oraz golden data w
`backend/tests/golden_data/security/misconfigurations/`.
