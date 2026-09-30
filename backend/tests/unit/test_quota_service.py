"""Tests for QuotaService — analysis quota checking (Story 1.10 Task 3, Story 7.1 Task 2b).

Model 3-planowy (CR#2): Freemium 10 / Basic 50 / Premium unlimited analiz.
Limity z ``subscription_plans.features`` (DB) przez cache procesowy —
hardcoded wartości tylko jako fallback awaryjny.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import QuotaExceededError
from app.models.tenant import PlanType
from app.services import quota_service
from app.services.quota_service import QuotaService, get_quota_service


@pytest.fixture(autouse=True)
def _clean_limits_cache():
    quota_service.clear_plan_limits_cache()
    yield
    quota_service.clear_plan_limits_cache()


@pytest.fixture
def mock_redis():
    return MagicMock()


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def service(mock_redis):
    return QuotaService(redis_client=mock_redis)


class TestCheckAnalysisQuota:
    def test_under_limit_returns_true(self, service, mock_redis, tenant_id):
        mock_redis.get.return_value = b"3"

        result = service.check_analysis_quota(tenant_id, plan=PlanType.FREEMIUM)

        assert result is True

    def test_at_limit_raises_quota_exceeded(self, service, mock_redis, tenant_id):
        mock_redis.get.return_value = b"10"

        with pytest.raises(QuotaExceededError) as exc_info:
            service.check_analysis_quota(tenant_id, plan=PlanType.FREEMIUM)

        body = exc_info.value.to_rfc7807()
        assert body["status"] == 429
        assert body["limit"] == 10
        assert body["used"] == 10
        assert body["plan"] == "freemium"
        assert "upgrade_url" in body

    def test_over_limit_raises_quota_exceeded(self, service, mock_redis, tenant_id):
        mock_redis.get.return_value = b"15"

        with pytest.raises(QuotaExceededError):
            service.check_analysis_quota(tenant_id, plan=PlanType.FREEMIUM)

    def test_basic_plan_limit_is_50(self, service, mock_redis, tenant_id):
        mock_redis.get.return_value = b"30"

        assert service.check_analysis_quota(tenant_id, plan=PlanType.BASIC) is True

        mock_redis.get.return_value = b"50"
        with pytest.raises(QuotaExceededError):
            service.check_analysis_quota(tenant_id, plan=PlanType.BASIC)

    def test_premium_plan_unlimited(self, service, mock_redis, tenant_id):
        mock_redis.get.return_value = b"999999"

        result = service.check_analysis_quota(tenant_id, plan=PlanType.PREMIUM)

        assert result is True

    def test_no_counter_yet_returns_true(self, service, mock_redis, tenant_id):
        mock_redis.get.return_value = None

        result = service.check_analysis_quota(tenant_id, plan=PlanType.FREEMIUM)

        assert result is True

    def test_redis_counter_key_format(self, service, mock_redis, tenant_id):
        mock_redis.get.return_value = None

        service.check_analysis_quota(tenant_id, plan=PlanType.FREEMIUM)

        call_args = mock_redis.get.call_args[0][0]
        assert call_args.startswith(f"tenant:{tenant_id}:analysis_count:")


class TestPlanLimitsSource:
    """7.1/2b.2 — jedno źródło prawdy: subscription_plans.features (DB) przez cache."""

    def test_limits_from_cache_not_hardcoded(self, service, mock_redis, tenant_id):
        quota_service.set_plan_limits_cache({PlanType.FREEMIUM: 7, PlanType.BASIC: 77, PlanType.PREMIUM: None})
        mock_redis.get.return_value = b"7"

        with pytest.raises(QuotaExceededError) as exc_info:
            service.check_analysis_quota(tenant_id, plan=PlanType.FREEMIUM)
        assert exc_info.value.to_rfc7807()["limit"] == 7

        mock_redis.get.return_value = b"70"
        assert service.check_analysis_quota(tenant_id, plan=PlanType.BASIC) is True

    def test_fallback_when_cache_empty(self, service, mock_redis, tenant_id):
        # Cache pusty (np. startup bez DB) → wartości awaryjne 10/50/unlimited
        mock_redis.get.return_value = b"10"
        with pytest.raises(QuotaExceededError):
            service.check_analysis_quota(tenant_id, plan=PlanType.FREEMIUM)

    def test_no_global_plan_limits_constant(self):
        # hardcoded PLAN_LIMITS usunięte (7.1/2b.2) — zostaje fallback awaryjny
        assert not hasattr(quota_service, "PLAN_LIMITS")
        assert quota_service.FALLBACK_ANALYSIS_LIMITS[PlanType.FREEMIUM] == 10
        assert quota_service.FALLBACK_ANALYSIS_LIMITS[PlanType.BASIC] == 50
        assert quota_service.FALLBACK_ANALYSIS_LIMITS[PlanType.PREMIUM] is None


class TestIncrementUsage:
    def test_increment_increases_counter(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 1

        result = service.increment_usage(tenant_id)

        assert result == 1
        call_key = mock_redis.incr.call_args[0][0]
        assert call_key.startswith(f"tenant:{tenant_id}:analysis_count:")

    def test_increment_sets_ttl_on_first_use(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        service.increment_usage(tenant_id)

        mock_redis.expire.assert_called_once()

    def test_increment_no_ttl_on_subsequent_use(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 5
        mock_redis.expire.return_value = True

        service.increment_usage(tenant_id)

        mock_redis.expire.assert_not_called()


class TestGetService:
    def test_get_quota_service_returns_instance(self):
        svc = get_quota_service()
        assert isinstance(svc, QuotaService)


class TestConcurrentReserve:
    """Story 7.8 (6.4): dwa równoczesne requesty przy liczniku = N-1.

    Atomowy INCR gwarantuje, że dokładnie jeden request dostaje ostatni slot,
    drugi dostaje 429 z rollbackiem (DECR) — brak TOCTOU.
    """

    def test_two_concurrent_requests_one_slot_left(self, tenant_id):
        import threading

        lock = threading.Lock()
        counters: dict[str, int] = {}

        class FakeAtomicRedis:
            def incr(self, key):
                with lock:
                    counters[key] = counters.get(key, 0) + 1
                    return counters[key]

            def decr(self, key):
                with lock:
                    counters[key] -= 1
                    return counters[key]

            def expire(self, key, ttl):
                return True

        service = QuotaService(redis_client=FakeAtomicRedis())
        # FREEMIUM limit 10 (fallback) — licznik na N-1 = 9, został 1 slot
        key = service._counter_key(tenant_id)
        counters[key] = 9

        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt():
            barrier.wait()
            try:
                service.check_and_reserve(tenant_id, plan=PlanType.FREEMIUM)
                results.append("ok")
            except QuotaExceededError:
                results.append("429")

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == ["429", "ok"]  # dokładnie jeden sukces
        assert counters[key] == 10  # rollback DECR przywrócił stan po odrzuceniu


class TestCheckAndReserve:
    def test_under_limit_increments_and_returns_count(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 3

        result = service.check_and_reserve(tenant_id, plan=PlanType.FREEMIUM)

        assert result == 3
        mock_redis.incr.assert_called_once()
        mock_redis.decr.assert_not_called()

    def test_at_limit_rolls_back_and_raises(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 11  # FREEMIUM limit 10

        with pytest.raises(QuotaExceededError) as exc_info:
            service.check_and_reserve(tenant_id, plan=PlanType.FREEMIUM)

        mock_redis.decr.assert_called_once()
        body = exc_info.value.to_rfc7807()
        assert body["status"] == 429
        assert body["used"] == 10  # count before this increment

    def test_first_increment_sets_ttl(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        service.check_and_reserve(tenant_id, plan=PlanType.FREEMIUM)

        mock_redis.expire.assert_called_once()

    def test_subsequent_increment_no_ttl(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 3

        service.check_and_reserve(tenant_id, plan=PlanType.FREEMIUM)

        mock_redis.expire.assert_not_called()

    def test_basic_plan_higher_limit(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 45

        result = service.check_and_reserve(tenant_id, plan=PlanType.BASIC)

        assert result == 45
        mock_redis.decr.assert_not_called()

    def test_premium_plan_unlimited_never_rolls_back(self, service, mock_redis, tenant_id):
        mock_redis.incr.return_value = 100_000

        result = service.check_and_reserve(tenant_id, plan=PlanType.PREMIUM)

        assert result == 100_000
        mock_redis.decr.assert_not_called()
