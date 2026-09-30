"""Uwierzytelnianie kluczem API — Story 8.6 (AC2, AC3, AC4).

Ścieżka równoległa do JWT: nagłówek ``Authorization: Bearer tgn_…`` jest
rozpoznawany po prefiksie, więc jedno pole nagłówka obsługuje oba rodzaje
poświadczeń bez zgadywania.

Klucz nie niesie roli ani MFA — kontekst tenanta i rola pochodzą z rekordu
``api_keys`` i powiązania ``user_tenants``. Scope ``read_only`` blokuje
metody zapisujące jeszcze przed wejściem w handler (AC3).
"""

import logging

from fastapi import Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NIL_UUID
from app.core.dependencies import _set_rls_context, _set_rls_tenant, get_db, get_redis
from app.core.exceptions import AuthError, ForbiddenError
from app.models.api_key import ApiKey, ApiKeyScope
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant
from app.services.auth.api_key_service import ApiKeyService, looks_like_api_key

logger = logging.getLogger(__name__)

# Metody niezmieniające stanu — dozwolone dla scope read_only (AC3).
_READ_ONLY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def extract_api_key(authorization: str | None) -> str | None:
    """Zwraca surowy klucz z nagłówka albo ``None``, gdy to nie klucz API."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    return token if looks_like_api_key(token) else None


async def authenticate_api_key(
    request: Request,
    raw_key: str,
    db: AsyncSession,
    redis: Redis | None = None,
) -> User:
    """Waliduje klucz i ustawia kontekst tenanta identyczny jak przy JWT.

    Rozróżnia trzy przyczyny odmowy (AC4): klucz nieznany, wygasły,
    odwołany — komunikat jest po polsku, bo trafia do logów CI/CD klienta.
    """
    # Lookup po hashu musi widzieć wiersze każdego tenanta — kontekst RLS
    # poznamy dopiero z samego klucza (jak w get_current_user).
    await _set_rls_tenant(db, NIL_UUID)

    service = ApiKeyService(db, redis=redis)
    api_key: ApiKey | None = await service.validate_api_key(raw_key)
    if api_key is None:
        raise AuthError("Nieprawidłowy klucz API")
    if api_key.revoked_at is not None:
        raise AuthError("API key został odwołany")
    if api_key.is_expired:
        raise AuthError("API key wygasł")

    # Scope sprawdzany przed handlerem — read_only nie dopuszcza zapisu (AC3).
    if api_key.scope == ApiKeyScope.READ_ONLY and request.method.upper() not in _READ_ONLY_METHODS:
        raise ForbiddenError("API key ma scope read-only")

    result = await db.execute(select(User).where(User.id == api_key.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or user.is_blocked:
        raise AuthError("Właściciel klucza API jest nieaktywny")

    # Rola z powiązania user↔tenant — klucz nie podnosi uprawnień właściciela.
    role_result = await db.execute(
        select(UserTenant.role).where(
            UserTenant.user_id == user.id,
            UserTenant.tenant_id == api_key.tenant_id,
        )
    )
    role_value = role_result.scalar_one_or_none()
    if role_value is None:
        raise AuthError("Klucz API wskazuje na firmę, do której użytkownik nie ma dostępu")
    role = role_value.value if isinstance(role_value, TenantRole) else str(role_value)

    tenant_id = api_key.tenant_id
    request.state.user = user
    request.state.tenant_id = tenant_id
    request.state.role = role
    request.state.is_admin = False  # klucz API nigdy nie działa jako admin platformy
    request.state.api_key_id = api_key.id
    request.state.api_key_scope = api_key.scope.value

    user._tenant_id = tenant_id  # type: ignore[attr-defined]
    user._tenant_role = role  # type: ignore[attr-defined]

    await _set_rls_context(db, tenant_id, is_admin=False)

    # Zapis znacznika użycia i wpis audytowy idą tym samym, dławionym rytmem
    # (AC6) — inaczej każdy request z pipeline'u generowałby wiersz w audycie.
    if await service.update_last_used(api_key.id):
        from app.services.admin.audit_service import log_action

        await log_action(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="api_key.used",
            resource_type="api_key",
            resource_id=api_key.id,
            changes={"key_prefix": api_key.key_prefix, "scope": api_key.scope.value},
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()

    return user


async def get_api_key_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    authorization: str | None = Header(None),
) -> User:
    """Dependency wymagająca klucza API (bez fallbacku na JWT)."""
    raw_key = extract_api_key(authorization)
    if raw_key is None:
        raise AuthError("Brak klucza API w nagłówku Authorization")
    return await authenticate_api_key(request, raw_key, db, redis)
