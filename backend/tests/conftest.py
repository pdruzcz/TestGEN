"""Shared test fixtures for TestGEN backend tests."""

import os

# Rate limiting (Story 7.8) wyłączony w testach — wspólny kubełek IP
# (ASGITransport) + realny Redis dałyby fałszywe 429 w dużych suite'ach.
# Testy middleware wstrzykują własny fake Redis (tests/middleware/).
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.main import create_app
from app.models.user_tenant import TenantRole
from tests.factories import make_tenant, make_user, make_user_tenant


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def mock_db():
    """Provides an AsyncMock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def tenant_a():
    return make_tenant(name="Company A")


@pytest.fixture
def tenant_b():
    return make_tenant(name="Company B")


@pytest.fixture
def owner_user(tenant_a):
    user = make_user(email="owner@companya.com", name="Owner A")
    ut = make_user_tenant(user_id=user.id, tenant_id=tenant_a.id, role=TenantRole.OWNER)
    user._user_tenant = ut
    user._tenant_id = tenant_a.id
    user._role = "owner"
    return user


@pytest.fixture
def regular_user(tenant_a):
    user = make_user(email="user@companya.com", name="User A")
    ut = make_user_tenant(user_id=user.id, tenant_id=tenant_a.id, role=TenantRole.USER)
    user._user_tenant = ut
    user._tenant_id = tenant_a.id
    user._role = "user"
    return user


@pytest.fixture
def admin_user(tenant_a):
    user = make_user(email="admin@testgen.io", name="Admin", is_admin=True)
    ut = make_user_tenant(user_id=user.id, tenant_id=tenant_a.id, role=TenantRole.OWNER)
    user._user_tenant = ut
    user._tenant_id = tenant_a.id
    user._role = "admin"
    user._is_admin = True
    return user


@pytest.fixture
def authenticated_app(app, owner_user, mock_db):
    """Returns app with authenticated owner and mocked DB."""

    async def _override_get_current_user():
        return owner_user

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(authenticated_app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as ac:
        yield ac
