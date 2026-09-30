# Integracje z trackerami (Jira, Azure DevOps)

> Pliki:
> - `backend/app/models/integration.py`
> - `backend/app/services/integrations/jira_service.py`
> - `backend/app/services/integrations/azure_devops_service.py`
> - `backend/app/api/routes/integrations.py`

## 1. Odpowiedzialność

Moduł integracji synchronizuje znaleziska gap analysis z zewnętrznymi trackerami
zadań, aby umożliwić zespołom pracę nad lukami w istniejącym przepływie (workflow)
bez konieczności ręcznego kopiowania informacji.

Dwóch dostawców:
- **Jira** (Cloud, REST API v3) — Story 5.8
- **Azure DevOps** (Cloud, Work Items API) — Story 5.9

## 2. Struktura danych

### 2.1 IntegrationConfig

```python
class IntegrationConfig(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "integration_configs"
    project_id: UUID           # FK → projects.id
    provider: IntegrationProvider  # jira | azure_devops
    base_url: str              # np. https://test.atlassian.net
    encrypted_credentials: str  # Fernet token {email:api_token}
    settings: dict             # np. {"project_key": "ENG", "issue_type": "Task"}
    is_active: bool
```

### 2.2 IntegrationSyncLog

```python
class IntegrationSyncLog(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "integration_sync_logs"
    integration_config_id: UUID
    provider: IntegrationProvider
    status: SyncStatus          # pending | running | success | failed | partial
    total_items: int
    synced_items: int
    failed_items: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    external_ids: dict          # {gap_finding_id: external_issue_key}
```

## 3. Szyfrowanie poświadczeń

`encrypted_credentials` przechowuje token Fernet (symmetric encryption) zawierający
JSON z polem `email` i `api_token`. Klucz przechowywany w zmiennej środowiskowej
`INTEGRATION_ENCRYPTION_KEY` (lub `FERNET_KEY` jako fallback).

```python
# Szyfrowanie przy zapisie
cipher_text = Fernet(key).encrypt(json.dumps({"email": ..., "api_token": ...}).encode())

# Odszyfrowanie przy użyciu
creds = json.loads(Fernet(key).decrypt(cipher_text))
```

## 4. JiraService

> Plik: `backend/app/services/integrations/jira_service.py`

### 4.1 Endpointy API

- `POST /serverinfo` — test połączenia
- `POST /issue` — tworzenie issue
- `GET /issue/{key}` — weryfikacja

### 4.2 Format issue

```json
{
  "fields": {
    "project": {"key": "ENG"},
    "summary": "[TestGEN] Missing: REQ-ANL-004 — export do PDF",
    "description": "...",
    "issuetype": {"name": "Task"},
    "priority": {"name": "High"},
    "labels": ["testgen", "gap-analysis"]
  }
}
```

Priorytet mapowany z gap severity:
- `critical` → "Highest"
- `warning` → "High"
- `info` → "Medium"

## 5. AzureDevOpsService

> Plik: `backend/app/services/integrations/azure_devops_service.py`

### 5.1 Endpointy API

- Uwierzytelnianie: PAT (Personal Access Token) przez Basic Auth
- `POST {org}/{project}/_apis/wit/workitems/$Task?api-version=7.0` — JSON Patch

### 5.2 Format work item

Azure DevOps używa JSON Patch (operacje `add`):

```json
[
  {"op": "add", "path": "/fields/System.Title", "value": "..."},
  {"op": "add", "path": "/fields/System.Description", "value": "..."},
  {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": 2},
  {"op": "add", "path": "/fields/System.Tags", "value": "testgen; gap-analysis"}
]
```

Priorytet mapowany 1–4 z gap severity.

## 6. Sync flow

1. Użytkownik konfiguruje integrację (URL + email + token) w Settings → Integrations.
2. Test połączenia (`POST /integrations/{provider}/test`).
3. W widoku gap-analysis wybiera findings i klika "Sync do Jira/ADO".
4. Backend tworzy `IntegrationSyncLog(status="pending")` i asynchronicznie:
   - Iteruje po findings
   - Dla każdego tworzy issue (lub pomija jeśli już istnieje external_id)
   - Aktualizuje `external_ids` map
   - Na koniec: `status="success"` (lub `"partial"` / `"failed"`)
5. UI pokazuje progress + wynik.

## 7. Deduplikacja

Pole `external_ids` w `IntegrationSyncLog` przechowuje mapę
`{gap_finding_id: external_issue_key}`. Ponowny sync pomija findings, które już
mają external_key, chyba że użytkownik wymusi overwrite.

## 8. Endpointy API

- `POST /projects/{project_id}/integrations/{provider}/configure` — zapis konfiguracji
- `POST /projects/{project_id}/integrations/{provider}/test` — test połączenia
- `POST /projects/{project_id}/integrations/{provider}/sync` — uruchomienie sync
- `GET /projects/{project_id}/integrations/sync-logs` — historia logów

## 9. Frontend

UI: `frontend/src/app/features/integrations/` — formularz konfiguracji (URL,
email, token, project_key), test connection button, lista sync logs z statusem
i licznikami (synced/failed).

## 10. Bezpieczeństwo

- Poświadczenia szyfrowane Fernet (at-rest)
- RLS per-tenant — integracja jest dostępna tylko dla członków tenant
- WALIDACJA URL: `base_url` musi być HTTPS w produkcji
- Rate limiting: max 10 syncs na godzinę per projekt (zapobieganie pętlom)

## 11. Testowanie

Testy jednostkowe: `backend/tests/unit/services/integrations/` (JiraService,
AzureDevOpsService — z httpx MockTransport).
Testy integracyjne: `backend/tests/integration/test_integrations_routes.py`.

## 12. Powiązane dokumenty

- [01 — Przegląd](01-overview.md)
- [02 — Przewodnik — integracje](../../../user-guide/luki-funkcjonalne/05-integracje-trackery.md)
