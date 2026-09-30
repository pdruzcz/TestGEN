"""RateLimitMiddleware — limit żądań per tenant w Redis (Story 7.8, AC2/AC5).

Fixed window per minutę: klucz ``ratelimit:{tenant_id}:{minute_ts}``,
``INCR`` + ``EXPIRE`` (Dev Notes 7.8 dopuszczają wariant counter z TTL).
Próg per plan z ``subscription_plans.features.rate_limit_per_min``
(Freemium 100 / Basic 100 / Premium 1000) — cache procesowy zasilany
przy seedzie (jedno źródło prawdy, wzorzec ``set_plan_limits_cache``);
fallback awaryjny z ``config_billing`` (RATE_LIMIT_BASIC/PROFESSIONAL).

Zasady (AC5):
- działa PRZED autoryzacją — tenant_id czytany z JWT best-effort
  (bez weryfikacji podpisu: identyfikacja kubełka, nie uwierzytelnienie;
  brak/śmieciowy token → kubełek per IP klienta);
- pomija: ``/webhooks/*``, ``/health``, ``/docs``, ``/openapi.json``;
- awaria Redis → fail-open (przepuszczamy; limit nie może położyć API).

Przekroczenie → 429 application/problem+json z headerami
``X-RateLimit-Limit`` / ``X-RateLimit-Remaining`` / ``X-RateLimit-Reset``
(epoch początku następnego okna) i ``Retry-After`` (AC2).
"""

import inspect
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
KEY_TTL_SECONDS = 120  # 2 okna — klucz znika sam po wyjściu z użycia

# Ścieżki wyłączone spod rate limitu (AC5).
EXEMPT_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")
# Story 8.1/8.2: webhooki GitHuba i GitLaba to dostawy od dostawcy, nie ruch
# tenanta — limit per IP zdusiłby serię zdarzeń z jednego repozytorium.
EXEMPT_SUBSTRINGS = (
    "/webhooks/",
    "/integrations/github/webhook",
    "/integrations/gitlab/webhook",
)

# Cache procesowy: plan → rate_limit_per_min z features (None = brak wpisu).
_rate_limits_cache: dict[str, int | None] = {}


def set_rate_limits_cache(limits: dict[str, int | None]) -> None:
    """Zasil cache progów z ``subscription_plans.features`` (seed/startup)."""
    _rate_limits_cache.clear()
    _rate_limits_cache.update(limits)


def rate_limit_for_plan(plan: str | None) -> int:
    """Próg req/min dla planu; nieznany/niezalogowany → próg podstawowy."""
    from app.core.config_billing import get_billing_settings

    if plan is not None and _rate_limits_cache.get(plan) is not None:
        return int(_rate_limits_cache[plan])  # type: ignore[arg-type]
    settings = get_billing_settings()
    if plan == "premium":
        return settings.rate_limit_professional
    return settings.rate_limit_basic


async def _tenant_for_api_key(raw_key: str) -> str | None:
    """Tenant klucza API — z cache procesowym TTL 60 s (Story 8.6, AC2).

    Kubełek limitu musi być per tenant, nie per klucz: pipeline z pięcioma
    kluczami nie może dostać pięciokrotnego limitu. Middleware nie może
    odpytywać DB co request, więc mapowanie hash→tenant jest cache'owane
    tym samym wzorcem co plan tenanta.
    """
    from app.core.security import hash_api_key

    key_hash = hash_api_key(raw_key)
    now = time.monotonic()
    cached = _api_key_tenant_cache.get(key_hash)
    if cached and cached[1] > now:
        return cached[0]

    tenant_id: str | None = None
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.core.database import get_engine
        from app.models.api_key import ApiKey

        async with AsyncSession(get_engine()) as session:
            result = await session.execute(
                select(ApiKey.tenant_id).where(
                    ApiKey.key_hash == key_hash,
                    ApiKey.revoked_at.is_(None),
                )
            )
            value = result.scalar_one_or_none()
            tenant_id = str(value) if value else None
    except Exception:
        return None

    _api_key_tenant_cache[key_hash] = (tenant_id, now + 60)
    return tenant_id


async def _default_identity(request) -> str | None:
    """Tenant_id z JWT albo z klucza API — best-effort, bez weryfikacji podpisu:
    służy wyłącznie do wyboru kubełka rate limitu (uwierzytelnienie i tak
    wykonuje ``get_current_user``/``api_key_auth`` za middleware'em)."""
    token: str | None = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:]
    elif request.cookies.get("access_token"):
        token = request.cookies["access_token"]
    if not token:
        return None
    # Klucz API (Story 8.6) nie jest JWT — tenant trzeba odczytać z bazy.
    if token.startswith("tgn_"):
        return await _tenant_for_api_key(token)
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        tenant_id = payload.get("tenant_id")
        return str(uuid.UUID(str(tenant_id))) if tenant_id else None
    except Exception:
        return None


async def _default_plan_resolver(tenant_id: str) -> str | None:
    """Plan tenanta z DB (legacy kolumna ``tenants.plan``, sync z subskrypcją)
    — z cache procesowym TTL 60 s (middleware nie może odpytywać DB co request)."""
    now = time.monotonic()
    cached = _tenant_plan_cache.get(tenant_id)
    if cached and cached[1] > now:
        return cached[0]
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.core.database import get_engine
        from app.models.tenant import Tenant

        async with AsyncSession(get_engine()) as session:
            result = await session.execute(select(Tenant.plan).where(Tenant.id == uuid.UUID(tenant_id)))
            plan = result.scalar_one_or_none()
    except Exception:
        return None
    plan_name = plan.value if hasattr(plan, "value") else (str(plan) if plan else None)
    _tenant_plan_cache[tenant_id] = (plan_name, now + 60)
    return plan_name


_tenant_plan_cache: dict[str, tuple[str | None, float]] = {}
# hash klucza API → tenant_id (Story 8.6, AC2)
_api_key_tenant_cache: dict[str, tuple[str | None, float]] = {}


async def _default_redis_factory():
    from app.core.redis import get_redis

    return await get_redis()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting per tenant_id (AC2) przed autoryzacją (AC5)."""

    def __init__(
        self,
        app,
        *,
        redis_factory: Callable[[], Awaitable] | None = None,
        plan_resolver: Callable[[str], Awaitable[str | None]] | None = None,
        identity_resolver: Callable[[Request], str | None] | None = None,
    ) -> None:
        super().__init__(app)
        self._redis_factory = redis_factory or _default_redis_factory
        self._plan_resolver = plan_resolver or _default_plan_resolver
        self._identity_resolver = identity_resolver or _default_identity

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.startswith(EXEMPT_PREFIXES) or any(s in path for s in EXEMPT_SUBSTRINGS):
            return await call_next(request)

        tenant_id = self._identity_resolver(request)
        if inspect.isawaitable(tenant_id):  # domyślny resolver jest async (lookup klucza API)
            tenant_id = await tenant_id
        if tenant_id:
            identity = tenant_id
            plan = await self._plan_resolver(tenant_id)
        else:
            client_host = request.client.host if request.client else "unknown"
            identity = f"ip:{client_host}"
            plan = None

        limit = rate_limit_for_plan(plan)
        now = int(time.time())
        window_start = now - (now % WINDOW_SECONDS)
        reset_at = window_start + WINDOW_SECONDS
        key = f"ratelimit:{identity}:{window_start}"

        try:
            redis = await self._redis_factory()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, KEY_TTL_SECONDS)
        except Exception as exc:  # fail-open — Redis nie może położyć API
            logger.warning("Rate limit pominięty (Redis niedostępny): %s", exc)
            return await call_next(request)

        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(limit - count, 0)),
            "X-RateLimit-Reset": str(reset_at),
        }

        if count > limit:
            retry_after = max(reset_at - now, 1)
            return JSONResponse(
                status_code=429,
                content={
                    "type": "https://testgen.dev/errors/rate-limit-exceeded",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": f"Przekroczono limit {limit} żądań/min dla planu — spróbuj ponownie za {retry_after}s",
                    "instance": path,
                    "error": "rate_limit_exceeded",
                    "plan": plan,
                    "limit": limit,
                },
                media_type="application/problem+json",
                headers={**headers, "Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        for name, value in headers.items():
            response.headers[name] = value
        return response
