"""API tests — Story 7.11 (AC3/AC5): /notifications + preferencje profilu.

DB mockowana; NotificationService patchowany (wzorzec test_billing_usage_dashboard).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.notification import Notification, NotificationSeverity, NotificationType
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = uuid.uuid4()
    user._tenant_id = _tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = _tenant_id
        request.state.role = "owner"
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _notification(user_id, *, is_read=False, threshold=80) -> Notification:
    return Notification(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=user_id,
        type=NotificationType.LIMIT_WARNING,
        severity=NotificationSeverity.CRITICAL if threshold >= 100 else NotificationSeverity.WARNING,
        title="Limit analiz osiągnięty" if threshold >= 100 else "Zbliżasz się do limitu analiz",
        message="Wykorzystujesz 80% limitu zasobu analiz.",
        resource_type="analyses",
        current_value=8,
        limit_value=10,
        percentage=threshold,
        threshold_percentage=threshold,
        billing_period=datetime.now(UTC).strftime("%Y-%m"),
        is_read=is_read,
        cta_url="/billing/plans",
        created_at=datetime.now(UTC),
    )


class TestListNotifications:
    async def test_lista_z_paginacja(self, client, app):
        db = AsyncMock()
        user = make_user()
        _override_auth(app, user, db)
        rows = [_notification(user.id), _notification(user.id, is_read=True)]

        with patch("app.services.notification_service.NotificationService") as mock_cls:
            svc = MagicMock()
            svc.get_notifications = AsyncMock(return_value=(rows, 7))
            mock_cls.return_value = svc

            resp = await client.get("/api/v1/notifications", params={"page": 1, "size": 2})

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 7
        assert body["page"] == 1
        assert body["size"] == 2
        assert len(body["items"]) == 2
        item = body["items"][0]
        assert set(item) >= {
            "id",
            "type",
            "severity",
            "title",
            "message",
            "resource_type",
            "percentage",
            "is_read",
            "cta_url",
            "created_at",
        }
        assert item["type"] == "limit_warning"
        assert item["cta_url"] == "/billing/plans"


class TestUnreadCount:
    async def test_licznik_nieprzeczytanych(self, client, app):
        db = AsyncMock()
        user = make_user()
        _override_auth(app, user, db)

        with patch("app.services.notification_service.NotificationService") as mock_cls:
            svc = MagicMock()
            svc.get_unread_count = AsyncMock(return_value=3)
            mock_cls.return_value = svc

            resp = await client.get("/api/v1/notifications/unread-count")

        assert resp.status_code == 200
        assert resp.json() == {"count": 3}


class TestMarkAsRead:
    async def test_oznacz_jedno(self, client, app):
        db = AsyncMock()
        user = make_user()
        _override_auth(app, user, db)
        n = _notification(user.id, is_read=True)  # serwis zwraca oznaczone

        with patch("app.services.notification_service.NotificationService") as mock_cls:
            svc = MagicMock()
            svc.mark_as_read = AsyncMock(return_value=n)
            mock_cls.return_value = svc

            resp = await client.post(f"/api/v1/notifications/{n.id}/read")

        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    async def test_cudze_powiadomienie_404(self, client, app):
        from app.core.exceptions import NotFoundError

        db = AsyncMock()
        user = make_user()
        _override_auth(app, user, db)

        with patch("app.services.notification_service.NotificationService") as mock_cls:
            svc = MagicMock()
            svc.mark_as_read = AsyncMock(side_effect=NotFoundError("Notification not found"))
            mock_cls.return_value = svc

            resp = await client.post(f"/api/v1/notifications/{uuid.uuid4()}/read")

        assert resp.status_code == 404


class TestMarkAllAsRead:
    async def test_oznacz_wszystkie(self, client, app):
        db = AsyncMock()
        user = make_user()
        _override_auth(app, user, db)

        with patch("app.services.notification_service.NotificationService") as mock_cls:
            svc = MagicMock()
            svc.mark_all_as_read = AsyncMock(return_value=5)
            mock_cls.return_value = svc

            resp = await client.post("/api/v1/notifications/read-all")

        assert resp.status_code == 200
        assert resp.json() == {"updated": 5}


class TestNotificationPreferences:
    """AC5 — PUT /users/me (istniejący endpoint profilu) zapisuje preferencje."""

    async def test_put_me_aktualizuje_preferencje(self, client, app):
        db = AsyncMock()
        user = make_user()
        _override_auth(app, user, db)

        prefs = {"limit_warnings": {"email": False, "in_app": True}}
        user.notification_preferences = prefs  # serwis mutuje i zwraca ten sam obiekt
        with patch("app.api.routes.users.update_profile", AsyncMock(return_value=user)) as upd:
            resp = await client.put("/api/v1/users/me", json={"notification_preferences": prefs})

        assert resp.status_code == 200
        upd.assert_awaited_once()
        assert upd.await_args.kwargs.get("notification_preferences") == prefs
        assert resp.json()["notification_preferences"] == prefs
