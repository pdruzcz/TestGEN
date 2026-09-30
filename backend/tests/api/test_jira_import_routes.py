"""API testy importu z Jiry — Story 8.12 (Task 6.3).

DB mockowana, klient Jiry i zadanie Celery patchowane.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.integration import IntegrationConfig, IntegrationProvider
from app.models.jira_import import JiraImport, JiraImportStatus
from app.models.project import Project, ProjectStatus
from app.services.integrations.jira_service import JiraImportError
from tests.factories import make_user

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _db() -> AsyncMock:
    db = AsyncMock()

    def _add(obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = NOW

    db.add = MagicMock(side_effect=_add)
    return db


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _rows(items) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = list(items)
    return r


def _sequence(db: AsyncMock, *results) -> None:
    pending = list(results)

    def _next(*args, **kwargs):
        return pending.pop(0) if pending else _scalar(None)

    db.execute.side_effect = _next


def _override(app, db) -> tuple[uuid.UUID, uuid.UUID]:
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    user = make_user(email="qa@firma.pl", name="QA")
    tenant_id = uuid.uuid4()
    user._tenant_id = tenant_id
    project_id = uuid.uuid4()

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = "owner"
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return tenant_id, project_id


def _project(project_id, tenant_id) -> Project:
    return Project(
        id=project_id,
        tenant_id=tenant_id,
        name="Projekt",
        status=ProjectStatus.ACTIVE,
        is_deleted=False,
        created_at=NOW,
    )


def _integration(project_id, tenant_id, provider=IntegrationProvider.JIRA) -> IntegrationConfig:
    from app.core.encryption import encrypt

    return IntegrationConfig(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        project_id=project_id,
        provider=provider,
        base_url="https://firma.atlassian.net",
        encrypted_credentials=encrypt("qa@firma.pl:token"),
        settings={"project_key": "QA"},
        is_active=True,
        created_at=NOW,
    )


def _import(project_id, tenant_id, **overrides) -> JiraImport:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "project_id": project_id,
        "integration_id": uuid.uuid4(),
        "jira_project_key": "QA",
        "issue_types": ["Story", "Epic"],
        "status": JiraImportStatus.COMPLETED,
        "last_import_at": NOW,
        "total_imported": 12,
        "total_attachments": 3,
        "total_skipped": 1,
        "created_at": NOW,
    }
    defaults.update(overrides)
    return JiraImport(**defaults)


# ── lista projektów Jiry ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lista_projektow_pochodzi_z_jiry(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(_integration(project_id, tenant_id)))

    with patch(
        "app.api.routes.jira_import.JiraImportClient",
        return_value=MagicMock(
            list_projects=AsyncMock(return_value=[{"key": "QA", "name": "Jakość"}])
        ),
    ):
        response = await client.get(f"/api/v1/projects/{project_id}/import/jira/projects")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["key"] == "QA"


@pytest.mark.asyncio
async def test_brak_integracji_daje_404(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(None))

    response = await client.get(f"/api/v1/projects/{project_id}/import/jira/projects")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_blad_jiry_nie_wychodzi_jako_500(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(_integration(project_id, tenant_id)))

    with patch(
        "app.api.routes.jira_import.JiraImportClient",
        return_value=MagicMock(
            list_projects=AsyncMock(side_effect=JiraImportError("Jira odrzuciła poświadczenia"))
        ),
    ):
        response = await client.get(f"/api/v1/projects/{project_id}/import/jira/projects")

    assert response.status_code == 422
    assert "poświadczenia" in response.text


# ── start importu ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_kolejkuje_zadanie(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalar(_integration(project_id, tenant_id)),
        _scalar(None),
    )

    with patch("app.workers.tasks.jira_import_tasks.import_from_jira_task.delay") as delay:
        delay.return_value = MagicMock(id="zadanie-1")
        response = await client.post(
            f"/api/v1/projects/{project_id}/import/jira",
            json={"jira_project_key": "QA", "issue_types": ["Story", "Bug"]},
        )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["task_id"] == "zadanie-1"
    assert body["status_url"] == "/api/v1/tasks/zadanie-1"
    delay.assert_called_once()


@pytest.mark.asyncio
async def test_nieobslugiwany_typ_zgloszenia_jest_odrzucany(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(_integration(project_id, tenant_id)))

    response = await client.post(
        f"/api/v1/projects/{project_id}/import/jira",
        json={"jira_project_key": "QA", "issue_types": ["Spike"]},
    )

    assert response.status_code == 422
    assert "Spike" in response.text


@pytest.mark.asyncio
async def test_pelny_reimport_kasuje_znacznik_ostatniego_importu(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    record = _import(project_id, tenant_id)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalar(_integration(project_id, tenant_id)),
        _scalar(record),
    )

    with patch("app.workers.tasks.jira_import_tasks.import_from_jira_task.delay") as delay:
        delay.return_value = MagicMock(id="zadanie-2")
        response = await client.post(
            f"/api/v1/projects/{project_id}/import/jira",
            json={"jira_project_key": "QA", "full_reimport": True},
        )

    assert response.status_code == 202, response.text
    # Bez wyzerowania znacznika „pełny" import i tak pobrałby tylko zmiany.
    assert record.last_import_at is None


@pytest.mark.asyncio
async def test_ponowny_import_nie_tworzy_drugiego_wpisu(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    record = _import(project_id, tenant_id)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalar(_integration(project_id, tenant_id)),
        _scalar(record),
    )

    with patch("app.workers.tasks.jira_import_tasks.import_from_jira_task.delay") as delay:
        delay.return_value = MagicMock(id="zadanie-3")
        response = await client.post(
            f"/api/v1/projects/{project_id}/import/jira",
            json={"jira_project_key": "QA"},
        )

    assert response.json()["import_id"] == str(record.id)
    # Dodany został wyłącznie wpis audytu — drugi JiraImport zgubiłby
    # znacznik ostatniego importu i przyrostowy przestałby być przyrostowy.
    added = [call[0][0] for call in db.add.call_args_list]
    assert not [obj for obj in added if isinstance(obj, JiraImport)]


@pytest.mark.asyncio
async def test_data_z_zadania_zastepuje_znacznik(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    record = _import(project_id, tenant_id)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalar(_integration(project_id, tenant_id)),
        _scalar(record),
    )

    with patch("app.workers.tasks.jira_import_tasks.import_from_jira_task.delay") as delay:
        delay.return_value = MagicMock(id="zadanie-4")
        await client.post(
            f"/api/v1/projects/{project_id}/import/jira",
            json={"jira_project_key": "QA", "updated_after": "2026-01-01T00:00:00Z"},
        )

    assert record.last_import_at.year == 2026
    assert record.last_import_at.month == 1


# ── stan importu ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_zwraca_liczniki(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _rows([_import(project_id, tenant_id)]))

    response = await client.get(f"/api/v1/projects/{project_id}/import/jira/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body[0]["total_imported"] == 12
    assert body[0]["total_attachments"] == 3
    assert body[0]["total_skipped"] == 1
    assert body[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_status_bez_importow_zwraca_pusta_liste(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _rows([]))

    response = await client.get(f"/api/v1/projects/{project_id}/import/jira/status")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_obcy_projekt_daje_404(app, client):
    db = _db()
    _override(app, db)
    _sequence(db, _scalar(None))

    response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/import/jira/status")

    assert response.status_code == 404
