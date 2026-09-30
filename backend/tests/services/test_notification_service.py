"""Testy NotificationService — Story 7.11 (AC1-AC5; Task 7.1).

Wzorzec mockowania: test_quota_service_dashboard (DB AsyncMock,
sub-usługi patchowane). Email mockowany (bez Graph API); szablony
renderowane realnie (render-check AC2: temat/treść/CTA).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.models.notification import (
    Notification,
    NotificationSeverity,
    NotificationType,
)
from app.models.tenant import PlanType, Tenant
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant
from app.services.notification_service import (
    NOTIFICATION_RESOURCES,
    NotificationService,
)

# --- fabryki ---


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _scalar(item):
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _tenant(plan: PlanType = PlanType.FREEMIUM) -> Tenant:
    return Tenant(
        id=uuid.uuid4(),
        name="Acme",
        slug=f"acme-{uuid.uuid4().hex[:8]}",
        plan=plan,
        is_active=True,
    )


def _user(pref: dict | None = None) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"owner-{uuid.uuid4().hex[:6]}@testgen.pl",
        password_hash="x",
        name="Owner",
        is_active=True,
        notification_preferences=pref if pref is not None else {},
    )


def _owner_link(tenant_id, user_id) -> UserTenant:
    return UserTenant(id=uuid.uuid4(), user_id=user_id, tenant_id=tenant_id, role=TenantRole.OWNER)


def _usage(entries: dict[str, dict | None]) -> dict:
    """Pełny kształt QuotaService.get_usage: None limit = unlimited."""
    full = {
        r.value: (entries.get(r.value) or {"used": 0, "limit": None, "percent": None}) for r in NOTIFICATION_RESOURCES
    }
    # pliki per analiza — stateless, ale get_usage je zwraca
    full.setdefault("files_per_analysis", {"used": 0, "limit": 5, "percent": 0.0})
    return full


def _notification(user_id, tenant_id, threshold=80, is_read=False) -> Notification:
    return Notification(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        type=NotificationType.LIMIT_WARNING,
        severity=NotificationSeverity.WARNING,
        title="Zbliżasz się do limitu analiz",
        message="Wykorzystujesz 80% limitu zasobu analiz.",
        resource_type="analyses",
        current_value=8,
        limit_value=10,
        percentage=80,
        threshold_percentage=threshold,
        billing_period=datetime.now(UTC).strftime("%Y-%m"),
        is_read=is_read,
        cta_url="/billing/plans",
    )


# --- AC1: progi 80/90/100 ---


class TestThresholds:
    async def test_prog_80_tworzy_ostrzezenie(self):
        db = _db()
        db.execute = AsyncMock(return_value=_scalar(None))  # dedup miss
        tenant = _tenant()
        owner = _user()
        svc = NotificationService(db)

        with (
            patch.object(svc, "_get_owner", AsyncMock(return_value=owner)),
            patch.object(
                svc,
                "_get_usage",
                AsyncMock(return_value=_usage({"analyses": {"used": 8, "limit": 10, "percent": 80.0}})),
            ),
        ):
            created = await svc._check_tenant_thresholds(tenant)

        assert len(created) == 1
        n = created[0]
        assert n.threshold_percentage == 80
        assert n.severity == NotificationSeverity.WARNING
        assert n.type == NotificationType.LIMIT_WARNING
        assert n.resource_type == "analyses"
        assert n.current_value == 8
        assert n.limit_value == 10
        assert n.percentage == 80
        assert n.is_read is False
        assert n.cta_url == "/billing/plans"

    async def test_skok_do_100_generuje_wszystkie_trzy_progi(self):
        db = _db()
        db.execute = AsyncMock(return_value=_scalar(None))
        tenant = _tenant()
        svc = NotificationService(db)

        with (
            patch.object(svc, "_get_owner", AsyncMock(return_value=_user())),
            patch.object(
                svc,
                "_get_usage",
                AsyncMock(return_value=_usage({"analyses": {"used": 10, "limit": 10, "percent": 100.0}})),
            ),
        ):
            created = await svc._check_tenant_thresholds(tenant)

        assert sorted(n.threshold_percentage for n in created) == [80, 90, 100]
        by_threshold = {n.threshold_percentage: n for n in created}
        assert by_threshold[90].severity == NotificationSeverity.WARNING
        assert by_threshold[100].severity == NotificationSeverity.CRITICAL

    async def test_unlimited_bez_powiadomien(self):
        db = _db()
        svc = NotificationService(db)
        with (
            patch.object(svc, "_get_owner", AsyncMock(return_value=_user())),
            patch.object(
                svc,
                "_get_usage",
                AsyncMock(return_value=_usage({"analyses": {"used": 9999, "limit": None, "percent": None}})),
            ),
        ):
            created = await svc._check_tenant_thresholds(_tenant())
        assert created == []

    async def test_files_per_analysis_nie_sa_sprawdzane(self):
        """Stateless (per analiza, 7.8) — nie jest zużyciem kumulatywnym."""
        db = _db()
        svc = NotificationService(db)
        usage = _usage({})
        usage["files_per_analysis"] = {"used": 5, "limit": 5, "percent": 100.0}
        with (
            patch.object(svc, "_get_owner", AsyncMock(return_value=_user())),
            patch.object(svc, "_get_usage", AsyncMock(return_value=usage)),
        ):
            created = await svc._check_tenant_thresholds(_tenant())
        assert created == []

    async def test_brak_ownera_pomija_tenanta(self):
        db = _db()
        svc = NotificationService(db)
        with patch.object(svc, "_get_owner", AsyncMock(return_value=None)):
            created = await svc._check_tenant_thresholds(_tenant())
        assert created == []


class TestDedup:
    """AC1: „każdy próg tylko RAZ per okres rozliczeniowy per zasób"."""

    async def test_istniejace_powiadomienie_pomijane(self):
        db = _db()
        tenant = _tenant()
        owner = _user()
        existing = _notification(owner.id, tenant.id, threshold=80)
        db.execute = AsyncMock(return_value=_scalar(existing))

        svc = NotificationService(db)
        result = await svc._create_notification(
            owner,
            tenant,
            "analyses",
            {"used": 8, "limit": 10, "percent": 80.0},
            threshold=80,
            plan_display="Freemium",
        )
        assert result is None
        db.add.assert_not_called()

    async def test_check_and_notify_agreguje_statystyki(self):
        db = _db()
        tenants = [_tenant(), _tenant()]
        db.execute = AsyncMock(return_value=_scalars(tenants))
        svc = NotificationService(db)
        created_stub = [_notification(uuid.uuid4(), t.id) for t in tenants for _ in range(2)]

        with (
            patch.object(svc, "_get_owner", AsyncMock(return_value=_user())),
            patch.object(
                svc,
                "_get_usage",
                AsyncMock(return_value=_usage({"analyses": {"used": 9, "limit": 10, "percent": 90.0}})),
            ),
            patch.object(svc, "_create_notification", AsyncMock(side_effect=created_stub)),
        ):
            stats = await svc.check_and_notify_thresholds()

        assert stats["tenants"] == 2
        # 9/10 → progi 80 i 90 per tenant
        assert stats["created"] == 4


# --- AC2: email ---


class TestEmail:
    async def test_email_wyslany_dla_nowego_powiadomienia(self):
        db = _db()
        owner = _user()
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None)])
        svc = NotificationService(db)

        with patch("app.services.notification_service.send_limit_warning_email") as send:
            n = await svc._create_notification(
                owner,
                _tenant(),
                "analyses",
                {"used": 8, "limit": 10, "percent": 80.0},
                threshold=80,
                plan_display="Freemium",
            )

        assert n is not None
        send.assert_called_once()
        kwargs = send.call_args.kwargs
        assert kwargs["subject"] == "TestGEN — zbliżasz się do limitu analiz"
        assert kwargs["threshold"] == 80

    async def test_email_temat_100_limit_osiagniety(self):
        db = _db()
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None)])
        svc = NotificationService(db)

        with patch("app.services.notification_service.send_limit_warning_email") as send:
            await svc._create_notification(
                _user(),
                _tenant(),
                "analyses",
                {"used": 10, "limit": 10, "percent": 100.0},
                threshold=100,
                plan_display="Freemium",
            )

        assert send.call_args.kwargs["subject"] == "TestGEN — limit analiz osiągnięty"

    async def test_email_wylaczony_preferencja(self):
        db = _db()
        owner = _user(pref={"limit_warnings": {"email": False, "in_app": True}})
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None)])
        svc = NotificationService(db)

        with patch("app.services.notification_service.send_limit_warning_email") as send:
            n = await svc._create_notification(
                owner,
                _tenant(),
                "analyses",
                {"used": 8, "limit": 10, "percent": 80.0},
                threshold=80,
                plan_display="Freemium",
            )

        assert n is not None  # rekord in-app powstaje mimo wyłączonego emaila
        send.assert_not_called()


# --- AC3/AC5: odczyt in-app + preferencje ---


class TestReadApis:
    async def test_get_unread_count(self):
        db = _db()
        db.execute = AsyncMock(return_value=_scalar(3))
        svc = NotificationService(db)
        with patch.object(svc, "_get_prefs", AsyncMock(return_value={})):
            assert await svc.get_unread_count(uuid.uuid4()) == 3

    async def test_get_notifications_paginacja(self):
        db = _db()
        rows = [_notification(uuid.uuid4(), uuid.uuid4()) for _ in range(2)]
        db.execute = AsyncMock(side_effect=[_scalars(rows), _scalar(5)])
        svc = NotificationService(db)
        with patch.object(svc, "_get_prefs", AsyncMock(return_value={})):
            items, total = await svc.get_notifications(uuid.uuid4(), page=2, size=2)
        assert items == rows
        assert total == 5

    async def test_mark_as_read(self):
        db = _db()
        user_id = uuid.uuid4()
        n = _notification(user_id, uuid.uuid4())
        db.execute = AsyncMock(return_value=_scalar(n))
        svc = NotificationService(db)
        result = await svc.mark_as_read(n.id, user_id)
        assert result.is_read is True

    async def test_mark_as_read_cudze_powiadomienie_404(self):
        db = _db()
        db.execute = AsyncMock(return_value=_scalar(None))
        svc = NotificationService(db)
        with pytest.raises(NotFoundError):
            await svc.mark_as_read(uuid.uuid4(), uuid.uuid4())

    async def test_mark_all_as_read(self):
        db = _db()
        db.execute = AsyncMock(return_value=MagicMock(rowcount=7))
        svc = NotificationService(db)
        assert await svc.mark_all_as_read(uuid.uuid4()) == 7

    async def test_in_app_wylaczone_ukrywa_liste(self):
        """AC5 — preferencja in_app=false: lista pusta, licznik 0."""
        db = _db()
        owner = _user(pref={"limit_warnings": {"email": True, "in_app": False}})
        svc = NotificationService(db)
        with patch.object(svc, "_get_prefs", AsyncMock(return_value=owner.notification_preferences)):
            items, total = await svc.get_notifications(owner.id)
            assert items == [] and total == 0
            assert await svc.get_unread_count(owner.id) == 0

    async def test_domyslne_preferencje_wlaczone(self):
        """AC5 — brak zapisanych preferencji = oba kanały aktywne."""
        db = _db()
        owner = _user(pref={})
        db.execute = AsyncMock(return_value=_scalar(2))
        svc = NotificationService(db)
        with patch.object(svc, "_get_prefs", AsyncMock(return_value=owner.notification_preferences)):
            assert await svc.get_unread_count(owner.id) == 2


# --- AC2: render szablonów (realny Jinja2) ---


class TestTemplates:
    def test_szablon_80_renders_context(self):
        from app.services.notification_service import render_limit_warning_body

        html = render_limit_warning_body(
            threshold=80,
            resource_display="analiz",
            current_display="8",
            limit_display="10",
            percentage=80,
            plan_display="Freemium",
            cta_url="http://localhost:4200/billing/plans",
        )
        assert "80%" in html
        assert "analiz" in html
        assert "Freemium" in html
        assert "/billing/plans" in html
        assert "Uaktualnij plan" in html
