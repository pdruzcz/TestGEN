import uuid
from collections.abc import AsyncGenerator, Callable

import jwt
from fastapi import Cookie, Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NIL_UUID
from app.core.database import get_db as _get_db
from app.core.exceptions import AuthError, ForbiddenError
from app.core.redis import get_redis as _get_redis
from app.models.user import User
from app.services.auth.jwt_handler import decode_token
from app.services.auth.token_store import is_access_token_blacklisted, is_tenant_membership_revoked
from app.services.billing.providers.base import PaymentProvider


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in _get_db():
        yield session


async def get_redis() -> Redis:
    return await _get_redis()


def get_payment_provider(redis: Redis = Depends(get_redis)) -> PaymentProvider:
    """Wybór dostawcy płatności z konfiguracji (Story 7.4, AC8).

    Jedyny provider: tpay (D1). Pole ``billing_provider`` w env pozwoli
    przesądzić wybór, gdy pojawi się drugi dostawca (ekspansja UE).
    """
    from app.core.config_billing import get_billing_settings
    from app.services.billing.providers.tpay import TpayProvider

    settings = get_billing_settings()
    provider_name = getattr(settings, "billing_provider", "tpay")
    if provider_name != "tpay":  # furtka pod ekspansję UE (Stripe) — na razie tylko tpay
        raise ValueError(f"Unknown payment provider: {provider_name} (only 'tpay' supported)")
    return TpayProvider(settings, redis=redis)


def get_quota_service(db: AsyncSession = Depends(get_db)):
    """QuotaService — egzekwowanie limitów per plan (Story 7.8, AC1)."""
    from app.services.billing.quota_service import QuotaService

    return QuotaService(db)


def get_notification_service(db: AsyncSession = Depends(get_db)):
    """NotificationService — powiadomienia o limitach (Story 7.11, AC3)."""
    from app.services.notification_service import NotificationService

    return NotificationService(db)


async def _set_rls_tenant(db: AsyncSession, tenant_id: uuid.UUID | str) -> None:
    """SET LOCAL with literal UUID — PostgreSQL SET doesn't support bind parameters.

    HOTFIX (izolacja tenantów, 2026-09-15): RLS jest nieskuteczne, gdy rola
    DB ma BYPASSRLS/SUPERUSER. Obok zmiennej sesyjnej zapisujemy jawny scope
    w ``db.info`` — serwisy (project_service, upload_service) dokładają filtr
    ``tenant_id`` w SQL na jego podstawie. NIL UUID (admin/system) = bez filtra.
    """
    safe_id = str(uuid.UUID(str(tenant_id)))
    await db.execute(text(f"SET LOCAL app.current_tenant = '{safe_id}'"))
    if safe_id == str(NIL_UUID):
        db.info["tenant_scope"] = None
    else:
        db.info["tenant_scope"] = safe_id


async def _set_rls_context(db: AsyncSession, tenant_id: uuid.UUID, is_admin: bool) -> None:
    """Set RLS tenant context. Admin bypasses RLS via nil UUID (won't match any real tenant).

    Uses SET LOCAL (transaction-scoped) to avoid connection pool contamination.
    """
    if is_admin:
        await _set_rls_tenant(db, NIL_UUID)
        return
    await _set_rls_tenant(db, tenant_id)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
) -> User:
    """Uwierzytelnienie użytkownika: JWT (cookie lub nagłówek) albo klucz API.

    Story 8.6 (AC2): klucz API rozpoznajemy po prefiksie ``tgn_`` i obsługujemy
    tutaj, a nie w osobnej zależności. Osobna zależność wymagałaby przepinania
    jej na każdym endpoincie z osobna — a klucz ma działać wszędzie tam, gdzie
    działa sesja, bo po to powstał (automatyzacja CI/CD, Story 8.4).

    Endpointy, które muszą odrzucać klucze API (zarządzanie samymi kluczami,
    webhooki), dokładają zależność :func:`require_session`.
    """
    from app.core.api_key_auth import authenticate_api_key, extract_api_key

    raw_api_key = extract_api_key(authorization)
    if raw_api_key is not None:
        return await authenticate_api_key(request, raw_api_key, db, redis)

    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif access_token:
        token = access_token

    if not token:
        raise AuthError("Missing authentication token")

    try:
        payload = decode_token(token)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise AuthError("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise AuthError("Invalid token type")

    jti = payload.get("jti")
    if jti and await is_access_token_blacklisted(redis, jti):
        raise AuthError("Token has been revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Invalid token payload")

    # Store tenant_id and role from JWT for downstream use
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "user")
    is_admin = payload.get("is_admin", False)

    # Clear stale RLS context from connection pool before user lookup.
    await _set_rls_tenant(db, NIL_UUID)

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    # Story 6.15 (AC3): blokada odcina też aktywne tokeny — nie tylko login
    if not user or not user.is_active or user.is_blocked:
        raise AuthError("User not found or inactive")

    request.state.user = user
    request.state.tenant_id = uuid.UUID(tenant_id) if tenant_id else None
    request.state.role = role
    request.state.is_admin = is_admin

    # Attach tenant context to User instance so downstream services can access it
    # via actor._tenant_id / actor._tenant_role (used by project_service, celery tasks, etc.)
    user._tenant_id = uuid.UUID(tenant_id) if tenant_id else None  # type: ignore[attr-defined]
    user._tenant_role = role  # type: ignore[attr-defined]

    # Check if tenant membership was revoked (immediate invalidation after deactivation)
    if tenant_id and not is_admin and await is_tenant_membership_revoked(redis, user.id, uuid.UUID(tenant_id)):
        raise AuthError("Tenant access revoked")

    # Set RLS tenant context for subsequent queries in this transaction
    if tenant_id:
        await _set_rls_context(db, uuid.UUID(tenant_id), is_admin)

    return user


def get_tenant(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Extract tenant_id from request state (set by get_current_user from JWT)."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise AuthError("No tenant context in token")
    return tenant_id


def require_role(*roles: str) -> Callable:
    """Dependency factory that checks user role from JWT payload."""

    async def _check(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        is_admin = getattr(request.state, "is_admin", False)
        # Admin bypasses all role checks
        if is_admin:
            return current_user

        role = getattr(request.state, "role", "user")
        if role not in roles:
            raise ForbiddenError(f"Requires role: {', '.join(sorted(roles))}")
        return current_user

    return _check


async def get_current_user_or_api_key(
    current_user: User = Depends(get_current_user),
) -> User:
    """Alias zgodności — :func:`get_current_user` obsługuje już oba rodzaje poświadczeń.

    Zostawiony, żeby nie zmieniać kontraktu miejsc, które go importują.
    """
    return current_user


def require_session(request: Request, current_user: User = Depends(get_current_user)) -> User:
    """Odrzuca żądania uwierzytelnione kluczem API (Story 8.6).

    Chroni operacje, które kluczem nie powinny być wykonalne — przede wszystkim
    zakładanie kolejnych kluczy i webhooków: klucz full-access mógłby wtedy
    wyprodukować sobie następny i wynieść dane poza kontrolę właściciela.
    """
    if getattr(request.state, "api_key_id", None) is not None:
        raise ForbiddenError("Ta operacja wymaga zalogowanej sesji — klucz API nie wystarcza")
    return current_user
