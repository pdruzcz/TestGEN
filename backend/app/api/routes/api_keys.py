"""Endpointy kluczy API — Story 8.6 (AC1, AC5, AC6).

Zarządzanie kluczami wymaga sesji przeglądarkowej właściciela firmy
(``require_role("owner")``; admin platformy przechodzi z definicji) —
celowo nie da się utworzyć nowego klucza samym kluczem API, bo klucz
read-only mógłby wtedy wyprodukować sobie klucz full-access.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_redis, get_tenant, require_role, require_session
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
)
from app.services.admin.audit_service import log_action
from app.services.auth.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=CreateApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: CreateApiKeyRequest,
    request: Request,
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> CreateApiKeyResponse:
    """Tworzy klucz i zwraca go w postaci jawnej — jedyny raz (AC1)."""
    service = ApiKeyService(db, redis=redis)
    api_key, raw_key = await service.create_api_key(
        tenant_id=tenant_id,
        user_id=current_user.id,
        name=payload.name,
        scope=payload.scope,
        expires_at=payload.expires_at,
    )
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="api_key.created",
        resource_type="api_key",
        resource_id=api_key.id,
        changes={
            "name": api_key.name,
            "scope": api_key.scope.value,
            "key_prefix": api_key.key_prefix,
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        },
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(api_key)
    return CreateApiKeyResponse(key=raw_key, api_key=ApiKeyResponse.model_validate(api_key))


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyListResponse:
    """Lista kluczy firmy — aktywne, wygasłe i odwołane (AC5)."""
    service = ApiKeyService(db)
    keys = await service.list_api_keys(tenant_id)
    return ApiKeyListResponse(
        items=[ApiKeyResponse.model_validate(k) for k in keys],
        total=len(keys),
    )


@router.delete("/{key_id}", response_model=ApiKeyResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("owner")),
    _session: User = Depends(require_session),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyResponse:
    """Odwołuje klucz (soft delete — ``revoked_at``), AC5/AC6."""
    service = ApiKeyService(db)
    api_key = await service.revoke_api_key(key_id, tenant_id)
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="api_key.revoked",
        resource_type="api_key",
        resource_id=api_key.id,
        changes={"name": api_key.name, "key_prefix": api_key.key_prefix},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(api_key)
    return ApiKeyResponse.model_validate(api_key)
