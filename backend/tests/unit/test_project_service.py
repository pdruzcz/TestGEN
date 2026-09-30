"""Unit tests for project_service: CRUD, quota, RBAC, soft delete."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.models.project import ProjectStatus
from app.models.tenant import PlanType
from app.services.project.project_service import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)


def _exec_scalar_one_or_none(value):
    return MagicMock(scalar_one_or_none=MagicMock(return_value=value))


def _exec_scalar(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _exec_scalars_list(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    # HOTFIX izolacji tenantów: serwisy czytają scope z db.info["tenant_scope"]
    db.info = {}
    return db


@pytest.fixture()
def tenant_basic():
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.plan = PlanType.BASIC
    return tenant


@pytest.fixture()
def tenant_premium():
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.plan = PlanType.PREMIUM
    return tenant


@pytest.fixture()
def owner(tenant_basic):
    """Owner actor with _tenant_id and _tenant_role set (set by request.state via dependency)."""
    actor = MagicMock()
    actor.id = uuid.uuid4()
    actor._tenant_id = tenant_basic.id
    actor._tenant_role = "owner"
    actor.is_admin = False
    return actor


@pytest.fixture()
def regular(tenant_basic):
    """Regular user actor with _tenant_id and _tenant_role set."""
    actor = MagicMock()
    actor.id = uuid.uuid4()
    actor._tenant_id = tenant_basic.id
    actor._tenant_role = "user"
    actor.is_admin = False
    return actor


@pytest.fixture()
def admin():
    """Platform admin actor."""
    actor = MagicMock()
    actor.id = uuid.uuid4()
    actor._tenant_id = uuid.uuid4()
    actor._tenant_role = "admin"
    actor.is_admin = True
    return actor


class TestCreateProject:
    @patch("app.services.project.project_service.log_action", new_callable=AsyncMock)
    async def test_user_can_create_project(self, mock_log, mock_db, regular, tenant_basic):
        """AC1, AC6: any authenticated role (including User) can create."""
        mock_db.get = AsyncMock(return_value=tenant_basic)  # tenant check (RLS scope)
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(None),  # conflict check: no duplicate
            ]
        )

        project = await create_project(
            mock_db,
            regular,
            name="My Project",
            description="desc",
            language_hint="python",
            tenant_id=tenant_basic.id,
        )

        assert project.name == "My Project"
        assert project.description == "desc"
        assert project.language_hint == "python"
        assert project.status == ProjectStatus.CREATED
        assert project.tenant_id == tenant_basic.id
        mock_db.add.assert_called_once()
        mock_log.assert_called_once()

    @patch("app.services.project.project_service.log_action", new_callable=AsyncMock)
    async def test_owner_can_create_project(self, mock_log, mock_db, owner, tenant_basic):
        mock_db.get = AsyncMock(return_value=tenant_basic)
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(None),  # conflict check
            ]
        )
        project = await create_project(
            mock_db,
            owner,
            name="Proj",
            tenant_id=tenant_basic.id,
        )
        assert project.name == "Proj"

    @patch("app.services.project.project_service.log_action", new_callable=AsyncMock)
    async def test_no_project_quota_for_any_plan(self, mock_log, mock_db, owner, tenant_basic):
        """Story 7.1 (macierz 2026-08-28): projekty unlimited w każdym planie —
        tworzenie nie wykonuje count() quoty projektowej."""
        mock_db.get = AsyncMock(return_value=tenant_basic)
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(None),  # conflict check
            ]
        )
        project = await create_project(
            mock_db,
            owner,
            name="Many Project",
            tenant_id=tenant_basic.id,
        )
        assert project.name == "Many Project"

    @patch("app.services.project.project_service.log_action", new_callable=AsyncMock)
    async def test_duplicate_name_raises_conflict(self, mock_log, mock_db, owner, tenant_basic):
        existing = MagicMock()
        existing.id = uuid.uuid4()
        mock_db.get = AsyncMock(return_value=tenant_basic)
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar(0),
                _exec_scalar_one_or_none(existing),
            ]
        )
        with pytest.raises(ConflictError, match="already exists"):
            await create_project(
                mock_db,
                owner,
                name="Duplicate",
                tenant_id=tenant_basic.id,
            )

    async def test_tenant_not_found_raises(self, mock_db, owner, tenant_basic):
        mock_db.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="Tenant not found"):
            await create_project(
                mock_db,
                owner,
                name="Proj",
                tenant_id=tenant_basic.id,
            )


class TestListProjects:
    async def test_list_returns_tuple(self, mock_db, owner):
        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar(3),  # count
                _exec_scalars_list([MagicMock(), MagicMock(), MagicMock()]),
            ]
        )
        projects, total = await list_projects(mock_db, owner)
        assert total == 3
        assert len(projects) == 3

    async def test_list_invalid_sort_by_raises(self, mock_db, owner):
        with pytest.raises(ValidationError, match="Invalid sort_by"):
            await list_projects(mock_db, owner, sort_by="malicious; DROP")

    async def test_list_invalid_sort_order_raises(self, mock_db, owner):
        with pytest.raises(ValidationError, match="sort_order"):
            await list_projects(mock_db, owner, sort_order="xxx")

    async def test_list_applies_status_filter(self, mock_db, owner):
        mock_db.execute = AsyncMock(side_effect=[_exec_scalar(0), _exec_scalars_list([])])
        await list_projects(mock_db, owner, status="active")
        # If no exception, filter applied successfully
        assert mock_db.execute.await_count == 2


class TestGetProject:
    async def test_get_project_found(self, mock_db, owner):
        project = MagicMock()
        project.id = uuid.uuid4()
        mock_db.execute = AsyncMock(return_value=_exec_scalar_one_or_none(project))
        result = await get_project(mock_db, owner, project.id)
        assert result is project

    async def test_get_project_not_found(self, mock_db, owner):
        mock_db.execute = AsyncMock(return_value=_exec_scalar_one_or_none(None))
        with pytest.raises(NotFoundError, match="Project not found"):
            await get_project(mock_db, owner, uuid.uuid4())


class TestUpdateProject:
    @patch("app.services.project.project_service.log_action", new_callable=AsyncMock)
    async def test_owner_can_update(self, mock_log, mock_db, owner, tenant_basic):
        project = MagicMock()
        project.id = uuid.uuid4()
        project.tenant_id = tenant_basic.id
        project.name = "Old Name"
        project.description = None
        project.language_hint = None

        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),  # get existing
                _exec_scalar_one_or_none(None),  # conflict check
            ]
        )

        result = await update_project(mock_db, owner, project.id, name="New Name", description="New desc")
        assert result.name == "New Name"
        assert result.description == "New desc"
        mock_log.assert_called_once()

    async def test_regular_user_cannot_update(self, mock_db, regular):
        """AC6: User role cannot update."""
        with pytest.raises(ForbiddenError, match="owner or admin"):
            await update_project(mock_db, regular, uuid.uuid4(), name="x")

    async def test_update_not_found(self, mock_db, owner):
        mock_db.execute = AsyncMock(return_value=_exec_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await update_project(mock_db, owner, uuid.uuid4(), name="x")

    @patch("app.services.project.project_service.log_action", new_callable=AsyncMock)
    async def test_update_name_conflict(self, mock_log, mock_db, owner, tenant_basic):
        project = MagicMock()
        project.id = uuid.uuid4()
        project.tenant_id = tenant_basic.id
        project.name = "Old"
        project.description = None
        project.language_hint = None

        conflict = MagicMock()
        conflict.id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(project),
                _exec_scalar_one_or_none(conflict),
            ]
        )
        with pytest.raises(ConflictError, match="already exists"):
            await update_project(mock_db, owner, project.id, name="TakenName")

    @patch("app.services.project.project_service.log_action", new_callable=AsyncMock)
    async def test_update_noop_no_audit(self, mock_log, mock_db, owner, tenant_basic):
        """When no fields change, no audit entry should be written."""
        project = MagicMock()
        project.id = uuid.uuid4()
        project.tenant_id = tenant_basic.id
        project.name = "Same"
        project.description = "Same desc"
        project.language_hint = "python"

        mock_db.execute = AsyncMock(return_value=_exec_scalar_one_or_none(project))

        result = await update_project(
            mock_db,
            owner,
            project.id,
            name="Same",
            description="Same desc",
            language_hint="python",
        )
        assert result is project
        mock_log.assert_not_called()


class TestDeleteProject:
    @patch("app.services.project.project_service.log_action", new_callable=AsyncMock)
    async def test_owner_can_soft_delete(self, mock_log, mock_db, owner, tenant_basic):
        """AC5: DELETE marks is_deleted=True, deleted_at set."""
        project = MagicMock()
        project.id = uuid.uuid4()
        project.tenant_id = tenant_basic.id
        project.is_deleted = False
        project.deleted_at = None

        mock_db.execute = AsyncMock(return_value=_exec_scalar_one_or_none(project))

        await delete_project(mock_db, owner, project.id)
        assert project.is_deleted is True
        assert project.deleted_at is not None
        mock_log.assert_called_once()

    async def test_regular_user_cannot_delete(self, mock_db, regular):
        """AC6: User role cannot delete."""
        with pytest.raises(ForbiddenError, match="owner or admin"):
            await delete_project(mock_db, regular, uuid.uuid4())

    async def test_delete_not_found(self, mock_db, owner):
        mock_db.execute = AsyncMock(return_value=_exec_scalar_one_or_none(None))
        with pytest.raises(NotFoundError):
            await delete_project(mock_db, owner, uuid.uuid4())
