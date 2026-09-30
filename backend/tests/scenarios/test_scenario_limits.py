"""Scenariusze 13-14 (AC13) — limity, rate limiting i progi powiadomień.

E2E z mockami (Task 6.1):
- limit analiz Freemium (10/mies., jedno źródło prawdy: ``features`` 7.1):
  próba ponad limit → 429 ``limit_reached`` z body FE upgrade CTA
  (``upgrade_url``); FE pokazuje CTA (komponenty 7.8/7.13);
- progi powiadomień 80/90/100% (7.11): email (mock) + in-app (Notification)
  z deduplikacją per okres;
- rate limiting per plan (7.8, Redis — FakeRedis): 101. żądanie/min → 429
  z nagłówkami ``X-RateLimit-*`` i ``Retry-After``.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import QuotaExceededError
from app.middleware.rate_limit import RateLimitMiddleware, set_rate_limits_cache
from app.models.notification import Notification, NotificationSeverity
from app.models.subscription_plan import PlanName
from app.models.usage import CounterType
from app.services.billing.quota_service import QuotaService
from app.services.notification_service import NotificationService
from tests.factories import make_tenant, make_user
from tests.fixtures.billing_fixtures import (
    make_mock_db,
    make_plans,
    make_subscription,
    scalar,
    scalars,
)
from tests.fixtures.usage_fixtures import USAGE_LEVELS_PERCENT, counter_at


class TestScenario13AnalysisLimit:
    """AC13 — limit analiz: 429 z informacją o limicie + upgrade CTA."""

    async def test_analysis_over_limit_raises_429_with_upgrade_cta(self):
        plans = make_plans()
        freemium = plans[PlanName.FREEMIUM]
        tenant_id = uuid.uuid4()
        sub = make_subscription(freemium, tenant_id)

        # Jedno źródło prawdy limitów: features planu z seeda 7.1.
        assert freemium.features["analyses"] == 10
        assert USAGE_LEVELS_PERCENT == (0, 50, 80, 90, 100)

        exhausted = counter_at(100, limit=10)  # 10/10 = 100% limitu
        db = make_mock_db(scalar(sub), scalar(freemium), scalar(exhausted))
        with pytest.raises(QuotaExceededError) as excinfo:
            await QuotaService(db).enforce_quota(tenant_id, CounterType.ANALYSES)

        err = excinfo.value
        assert err.status_code == 429  # mapping API (RFC7807)
        assert err.extra["error"] == "limit_reached"
        assert err.extra["resource"] == "analyses"
        assert err.extra["limit"] == 10
        assert err.extra["current"] == 10
        assert err.extra["plan"] == "freemium"
        assert err.extra["upgrade_url"] == "/billing/plans"  # FE upgrade CTA

    async def test_below_limit_allows_and_at_80_percent_still_allows(self):
        plans = make_plans()
        freemium = plans[PlanName.FREEMIUM]
        tenant_id = uuid.uuid4()
        sub = make_subscription(freemium, tenant_id)

        for level in (0, 50, 80, 90):  # wszystko < 100% → dozwolone
            db = make_mock_db(scalar(sub), scalar(freemium), scalar(counter_at(level, limit=10)))
            assert await QuotaService(db).check_quota(tenant_id, CounterType.ANALYSES) is True


class TestScenario14NotificationThresholds:
    """AC13 — progi 80/90/100%: in-app + email (mock), deduplikacja."""

    def _db_for(self, *, tenant, owner, sub, plan, counter, dedup_results):
        return make_mock_db(
            scalars(tenant),  # skan aktywnych tenantów
            scalar(owner),  # _get_owner
            scalar(sub),  # get_usage: subskrypcja
            scalar(plan),  # get_usage: plan efektywny
            scalars(counter),  # get_usage: liczniki
            *dedup_results,  # dedup per (próg x zasób przekroczony)
        )

    async def test_threshold_80_creates_warning_notification_and_email(self):
        plans = make_plans()
        freemium = plans[PlanName.FREEMIUM]
        tenant = make_tenant(name="Threshold Co")
        owner = make_user(email="owner@threshold.pl")
        sub = make_subscription(freemium, tenant.id)
        counter = counter_at(80, limit=10, tenant_id=tenant.id)  # 8/10 = 80%

        db = self._db_for(
            tenant=tenant,
            owner=owner,
            sub=sub,
            plan=freemium,
            counter=counter,
            dedup_results=[scalar(None)],
        )
        with patch("app.services.notification_service.send_limit_warning_email") as send_email:
            stats = await NotificationService(db).check_and_notify_thresholds()

        assert stats == {"tenants": 1, "created": 1}
        notifications = [n.args[0] for n in db.add.call_args_list if isinstance(n.args[0], Notification)]
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.threshold_percentage == 80
        assert notification.severity == NotificationSeverity.WARNING
        assert notification.percentage == 80
        assert "Zbliżasz się" in notification.title  # próg < 100%
        assert notification.cta_url == "/billing/plans"
        send_email.assert_called_once()
        assert send_email.call_args.kwargs["to"] == "owner@threshold.pl"

    async def test_threshold_100_creates_all_three_with_critical(self):
        plans = make_plans()
        freemium = plans[PlanName.FREEMIUM]
        tenant = make_tenant(name="Limit Co")
        owner = make_user(email="owner@limit.pl")
        sub = make_subscription(freemium, tenant.id)
        counter = counter_at(100, limit=10, tenant_id=tenant.id)  # 10/10 → 80+90+100

        db = self._db_for(
            tenant=tenant,
            owner=owner,
            sub=sub,
            plan=freemium,
            counter=counter,
            dedup_results=[scalar(None), scalar(None), scalar(None)],
        )
        with patch("app.services.notification_service.send_limit_warning_email"):
            stats = await NotificationService(db).check_and_notify_thresholds()

        assert stats["created"] == 3  # progi 80, 90, 100 naraz
        notifications = [n.args[0] for n in db.add.call_args_list if isinstance(n.args[0], Notification)]
        by_threshold = {n.threshold_percentage: n for n in notifications}
        assert set(by_threshold) == {80, 90, 100}
        assert by_threshold[100].severity == NotificationSeverity.CRITICAL
        assert "osiągnięty" in by_threshold[100].title

    async def test_dedup_skips_already_notified_threshold_in_period(self):
        plans = make_plans()
        freemium = plans[PlanName.FREEMIUM]
        tenant = make_tenant(name="Dedup Co")
        owner = make_user(email="owner@dedup.pl")
        sub = make_subscription(freemium, tenant.id)
        counter = counter_at(80, limit=10, tenant_id=tenant.id)

        # Próg 80 już obsłużony w tym okresie → dedup (scalar zwraca id).
        db = self._db_for(
            tenant=tenant,
            owner=owner,
            sub=sub,
            plan=freemium,
            counter=counter,
            dedup_results=[scalar(uuid.uuid4())],
        )
        with patch("app.services.notification_service.send_limit_warning_email") as send_email:
            stats = await NotificationService(db).check_and_notify_thresholds()

        assert stats["created"] == 0
        send_email.assert_not_called()


class FakeRedis:
    """Minimalny async Redis (INCR + EXPIRE) — wzorzec tests/middleware."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, ttl: int) -> None:
        pass


class TestScenario14RateLimiting:
    """AC13 — 101. żądanie/min → 429 z nagłówkami X-RateLimit-* (Redis)."""

    def test_101st_request_in_minute_gets_429_with_headers(self):
        from unittest.mock import AsyncMock

        set_rate_limits_cache({"freemium": 100})  # próg z features (7.1)
        try:
            app = FastAPI()
            app.add_middleware(
                RateLimitMiddleware,
                redis_factory=AsyncMock(return_value=FakeRedis()),
                plan_resolver=AsyncMock(return_value="freemium"),
                identity_resolver=lambda request: "tenant-rate-test",
            )

            @app.get("/api/v1/projects")
            async def projects():
                return {"ok": True}

            with TestClient(app) as client:
                for i in range(100):
                    resp = client.get("/api/v1/projects")
                    assert resp.status_code == 200, f"żądanie {i + 1}"
                    assert resp.headers["X-RateLimit-Limit"] == "100"
                    assert resp.headers["X-RateLimit-Remaining"] == str(100 - (i + 1))
                    assert "X-RateLimit-Reset" in resp.headers

                # 101. żądanie w tej samej minucie → 429.
                limited = client.get("/api/v1/projects")
                assert limited.status_code == 429
                assert limited.headers["X-RateLimit-Limit"] == "100"
                assert limited.headers["X-RateLimit-Remaining"] == "0"
                assert "X-RateLimit-Reset" in limited.headers
                assert "Retry-After" in limited.headers
                body = limited.json()
                assert body["error"] == "rate_limit_exceeded"
                assert body["plan"] == "freemium"
                assert body["limit"] == 100
                assert limited.headers["content-type"].startswith("application/problem+json")
        finally:
            set_rate_limits_cache({})  # nie zanieczyszczaj innych testów
