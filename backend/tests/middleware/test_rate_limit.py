"""Testy RateLimitMiddleware — Story 7.8, Task 6.2 (AC2/AC5).

Fixed window per minutę w Redis (INCR + EXPIRE), próg per plan z
``features.rate_limit_per_min`` (Freemium/Basic 100, Premium 1000),
klucz per tenant_id z JWT (IP dla niezalogowanych), headery X-RateLimit-*,
pominięcia: /webhooks/*, /health, /docs, /openapi.json.
Redis i resolver planu wstrzykiwane — bez sieci.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import (
    RateLimitMiddleware,
    rate_limit_for_plan,
    set_rate_limits_cache,
)

TENANT_ID = str(uuid.uuid4())


class FakeRedis:
    """Minimalny async Redis: INCR + EXPIRE w pamięci."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, ttl: int) -> None:
        self.expirations[key] = ttl


def _app(
    *,
    plan: str | None = "basic",
    redis: FakeRedis | None = None,
    tenant_id: str | None = TENANT_ID,
) -> tuple[FastAPI, FakeRedis]:
    fake = redis or FakeRedis()
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        redis_factory=AsyncMock(return_value=fake),
        plan_resolver=AsyncMock(return_value=plan),
        identity_resolver=lambda request: tenant_id,
    )

    @app.get("/api/v1/projects")
    async def projects():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/v1/billing/webhooks/tpay")
    async def webhook():
        return {"ok": True}

    return app, fake


class TestRateLimitCache:
    def test_progi_z_cache_features(self):
        set_rate_limits_cache({"freemium": 100, "basic": 100, "premium": 1000})
        assert rate_limit_for_plan("premium") == 1000
        assert rate_limit_for_plan("basic") == 100
        set_rate_limits_cache({})

    def test_fallback_z_configu(self):
        set_rate_limits_cache({})
        assert rate_limit_for_plan("freemium") == 100
        assert rate_limit_for_plan("basic") == 100
        assert rate_limit_for_plan("premium") == 1000
        assert rate_limit_for_plan(None) == 100  # niezalogowany/nieznany


class TestRateLimitMiddleware:
    def test_przepuszcza_i_dodaje_headery_ac2(self):
        app, _ = _app(plan="basic")
        client = TestClient(app)
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "100"
        assert resp.headers["X-RateLimit-Remaining"] == "99"
        assert int(resp.headers["X-RateLimit-Reset"]) > 0

    def test_przekroczenie_zwraca_429_z_headerami(self):
        fake = FakeRedis()
        app, _ = _app(plan="basic", redis=fake)
        client = TestClient(app)
        # sztucznie napompuj licznik do limitu
        for key in list(fake.counts):
            del fake.counts[key]
        resp = None
        for _ in range(101):
            resp = client.get("/api/v1/projects")
        assert resp is not None
        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Limit"] == "100"
        assert resp.headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in resp.headers
        body = resp.json()
        assert body["status"] == 429

    def test_premium_ma_wyzszy_prog(self):
        app, _ = _app(plan="premium")
        client = TestClient(app)
        resp = client.get("/api/v1/projects")
        assert resp.headers["X-RateLimit-Limit"] == "1000"

    def test_klucz_per_tenant_id(self):
        fake = FakeRedis()
        app, _ = _app(plan="basic", redis=fake)
        TestClient(app).get("/api/v1/projects")
        assert len(fake.counts) == 1
        key = next(iter(fake.counts))
        assert key.startswith(f"ratelimit:{TENANT_ID}:")

    def test_niezalogowany_fallback_ip(self):
        fake = FakeRedis()
        app, _ = _app(plan=None, redis=fake, tenant_id=None)
        TestClient(app).get("/api/v1/projects")
        key = next(iter(fake.counts))
        # TestClient → client.host = "testclient"
        assert key.startswith("ratelimit:ip:")

    def test_pomija_health_webhooki_docs_ac5(self):
        fake = FakeRedis()
        app, _ = _app(redis=fake)
        client = TestClient(app)
        client.get("/health")
        client.post("/api/v1/billing/webhooks/tpay")
        client.get("/docs")
        client.get("/openapi.json")
        assert fake.counts == {}  # żaden exempt path nie liczony

    def test_redis_awaria_fail_open(self):
        """Awaria Redis nie może położyć API — przepuszczamy bez limitu."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            redis_factory=AsyncMock(side_effect=ConnectionError("redis down")),
            plan_resolver=AsyncMock(return_value="basic"),
            identity_resolver=lambda request: TENANT_ID,
        )

        @app.get("/api/v1/projects")
        async def projects():
            return {"ok": True}

        resp = TestClient(app).get("/api/v1/projects")
        assert resp.status_code == 200

    def test_expire_ustawiany_na_kluczu(self):
        fake = FakeRedis()
        app, _ = _app(redis=fake)
        TestClient(app).get("/api/v1/projects")
        assert list(fake.expirations.values()) == [120]


class TestIdentityFromJwt:
    @pytest.mark.asyncio
    async def test_domyslny_resolver_wyciaga_tenant_z_jwt(self):
        """Bez wstrzykniętego identity_resolver — dekodowanie JWT best-effort."""
        import jwt as pyjwt

        from app.middleware.rate_limit import _default_identity

        token = pyjwt.encode({"tenant_id": TENANT_ID}, "x" * 32, algorithm="HS256")
        req = SimpleNamespace(headers={"Authorization": "Bearer " + token}, cookies={}, client=None)

        assert await _default_identity(req) == TENANT_ID

    @pytest.mark.asyncio
    async def test_smieciowy_token_daje_none(self):
        from app.middleware.rate_limit import _default_identity

        req = SimpleNamespace(headers={"Authorization": "Bearer nie-jwt"}, cookies={}, client=None)

        assert await _default_identity(req) is None

    @pytest.mark.asyncio
    async def test_klucz_api_daje_kubelek_tenanta(self):
        """Story 8.6 (AC2): klucz ``tgn_`` → kubełek tenanta, nie per IP."""
        from app.middleware import rate_limit
        from app.middleware.rate_limit import _default_identity

        raw_key = "tgn_" + "a" * 64
        req = SimpleNamespace(headers={"Authorization": "Bearer " + raw_key}, cookies={}, client=None)

        with patch.object(
            rate_limit, "_tenant_for_api_key", AsyncMock(return_value=TENANT_ID)
        ) as lookup:
            assert await _default_identity(req) == TENANT_ID
        lookup.assert_awaited_once_with(raw_key)

    @pytest.mark.asyncio
    async def test_lookup_klucza_api_jest_cache_owany(self):
        """Middleware nie może odpytywać DB co request — drugi raz z cache."""
        from app.middleware import rate_limit
        from app.middleware.rate_limit import _tenant_for_api_key

        raw_key = "tgn_" + "b" * 64
        rate_limit._api_key_tenant_cache.clear()

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = uuid.UUID(TENANT_ID)
        session.execute.return_value = result
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("sqlalchemy.ext.asyncio.AsyncSession", return_value=session_cm), patch(
            "app.core.database.get_engine", MagicMock()
        ):
            assert await _tenant_for_api_key(raw_key) == TENANT_ID
            assert await _tenant_for_api_key(raw_key) == TENANT_ID

        session.execute.assert_awaited_once()  # drugie wywołanie z cache
        rate_limit._api_key_tenant_cache.clear()
