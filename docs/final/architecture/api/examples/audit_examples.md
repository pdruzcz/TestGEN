# Przykłady API — Logi audytowe (admin)

Logi audytowe są realizowane przez model **`AuditLog`** (`app/models/audit_log.py`,
tabela `audit_logs`) oraz serwis `app/services/admin/audit_service.py`
(`log_action`, `list_audit_logs`). Architektura:
[ADR-010](../../adr/ADR-010-audit-logging.md).

## Charakterystyka logów

- **Immutability** — logi nie mają `updated_at`; raz zapisane nie są modyfikowane.
- **Brak FK na `tenant_id`** — logi zachowują `tenant_id` nawet po usunięciu
  tenanta (zgodność/retencja).
- **Kontekst** — każdy wpis: `action`, `user_id`, `tenant_id`, `created_at`
  oraz payload szczegółów.

## Co jest logowane

- Zdarzenia auth: rejestracja, weryfikacja email, logowanie, wybór tenanta,
  refresh, wylogowanie, setup/weryfikacja/usunięcie MFA.
- Operacje wrażliwe: upload plików, uruchomienie analizy, akceptacja/odrzucenie
  przypadku testowego, usunięcie zasobów.
- Decyzje workflow ([ADR-009](../../adr/ADR-009-code-review-workflow.md)).

## Dostęp (rola admin)

Wgląd w logi mają role platformowe (Admin). Endpointy audytowe eksponowane są
pod tagiem admin — pełna lista parametrów i schemat odpowiedzi w
`/openapi.json` (tag `admin`). Zapytanie serwisu obsługuje filtry:

```python
from app.services.admin.audit_service import list_audit_logs

# Filtry: tenant_id, action, user_id (każdy opcjonalny)
entries = list_audit_logs(
    session=db_session,
    tenant_id=tenant_uuid,   # RLS: ograniczone do kontekstu
    action="test_case.review",
    user_id=user_uuid,
)
```

## Przykładowy kształt wpisu

```json
{
  "id": "uuid",
  "action": "test_case.review",
  "user_id": "uuid-użytkownika",
  "tenant_id": "uuid-tenanta",
  "details": {
    "test_case_id": "uuid",
    "decision": "approve",
    "comment": "Zgodny ze standardem"
  },
  "created_at": "2026-06-23T10:00:00Z"
}
```

## Powiązane

- [ADR-002](../../adr/ADR-002-multi-tenancy-rls.md) — kontekst tenanta w logach.
- [ADR-009](../../adr/ADR-009-code-review-workflow.md) — logowane decyzje
  przeglądu.
- `/openapi.json` (tag `admin`) — autorytatywna lista endpointów audytowych.
