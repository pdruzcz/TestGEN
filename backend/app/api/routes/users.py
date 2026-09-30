"""User management API routes."""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.redis import get_redis
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant
from app.schemas.auth import InviteResponse, InviteUserRequest, MessageResponse
from app.schemas.users import (
    ChangePasswordRequest,
    ChangeRoleRequest,
    ResetPasswordByTokenRequest,
    UpdateProfileRequest,
    UserListResponse,
    UserResponse,
)
from app.services.auth.auth_service import invite_user
from app.services.auth.token_store import revoke_tenant_membership
from app.services.user.user_service import (
    change_password,
    change_role,
    deactivate_user,
    reset_password,
    set_user_blocked,
    update_profile,
    use_password_reset_token,
)
from app.workers.tasks.email_tasks import send_invitation_email_task, send_password_reset_email_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


def _build_user_response(user: User, tenant_id: uuid.UUID, role: str, mfa_enabled: bool = False) -> UserResponse:
    """Build UserResponse from User + tenant context."""
    return UserResponse(
        id=user.id,
        tenant_id=tenant_id,
        email=user.email,
        name=user.name,
        role=role,
        is_active=user.is_active,
        is_blocked=bool(user.is_blocked),
        deleted_at=user.deleted_at,
        email_verified_at=user.email_verified_at,
        notification_preferences=user.notification_preferences or {},
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        mfa_enabled=mfa_enabled,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = request.state.tenant_id
    role = request.state.role

    from app.models.mfa import UserMFA

    mfa_result = await db.execute(
        select(UserMFA.is_enabled).where(UserMFA.user_id == current_user.id, UserMFA.is_enabled.is_(True))
    )
    mfa_enabled = mfa_result.scalar_one_or_none() is not None

    return _build_user_response(current_user, tenant_id, role, mfa_enabled)


@router.put("/me", response_model=UserResponse)
async def update_me(
    body: UpdateProfileRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = request.state.tenant_id
    role = request.state.role

    user = await update_profile(
        db,
        user_id=current_user.id,
        tenant_id=tenant_id,
        name=body.name,
        notification_preferences=body.notification_preferences,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return _build_user_response(user, tenant_id, role)


@router.put("/me/password", response_model=MessageResponse)
async def change_my_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = request.state.tenant_id
    await change_password(
        db,
        user_id=current_user.id,
        tenant_id=tenant_id,
        old_password=body.old_password,
        new_password=body.new_password,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"message": "Hasło zostało zmienione"}


@router.get("", response_model=UserListResponse)
async def list_users(
    response: Response,
    request: Request,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id_filter: uuid.UUID | None = Query(None, alias="tenant_id", description="Filter by tenant (admin only)"),
):
    is_admin = request.state.is_admin
    current_tenant_id = request.state.tenant_id

    # Admin can list cross-tenant with optional filter
    filter_tenant = tenant_id_filter if is_admin and tenant_id_filter else current_tenant_id

    # Query via UserTenant to get users for this tenant
    ut_stmt = select(UserTenant).where(UserTenant.tenant_id == filter_tenant)
    count_stmt = select(func.count()).select_from(ut_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    ut_stmt = ut_stmt.order_by(UserTenant.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ut_result = await db.execute(ut_stmt)
    user_tenants = list(ut_result.scalars().all())

    if not user_tenants:
        response.headers["X-Total-Count"] = "0"
        return UserListResponse(users=[], total=0)

    user_ids = [ut.user_id for ut in user_tenants]
    # Konta usunięte miękko nie pojawiają się na liście (Story 6.15, AC3)
    users_result = await db.execute(select(User).where(User.id.in_(user_ids), User.deleted_at.is_(None)))
    user_map = {u.id: u for u in users_result.scalars().all()}

    # Preserve order from user_tenants query
    user_responses = []
    for ut in user_tenants:
        user = user_map.get(ut.user_id)
        if user:
            user_responses.append(_build_user_response(user, ut.tenant_id, ut.role.value))

    response.headers["X-Total-Count"] = str(total)
    return UserListResponse(users=user_responses, total=total)


@router.post("/invite", status_code=201, response_model=InviteResponse)
async def invite(
    body: InviteUserRequest,
    request: Request,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = request.state.tenant_id
    role = request.state.role

    target_role = TenantRole(body.role.value)
    user, token = await invite_user(
        db,
        owner=current_user,
        owner_tenant_id=tenant_id,
        owner_role=role,
        email=body.email,
        role=target_role,
    )

    from app.models.tenant import Tenant

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    tenant_name = tenant.name if tenant else ""

    await db.commit()

    # Send invitation email only for new users (token is not None)
    if token:
        try:
            send_invitation_email_task.delay(user.email, token, current_user.name, tenant_name)
        except Exception:
            logger.exception("Failed to queue invitation email for %s", user.email)

    return {"message": "Zaproszenie zostało wysłane", "user_id": user.id}


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_role(
    user_id: uuid.UUID,
    body: ChangeRoleRequest,
    request: Request,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = request.state.tenant_id
    is_admin = request.state.is_admin

    new_role = TenantRole(body.role.value)
    user = await change_role(
        db,
        actor=current_user,
        target_user_id=user_id,
        new_role=new_role,
        current_tenant_id=tenant_id,
        is_admin=is_admin,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return _build_user_response(user, tenant_id, new_role.value)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    tenant_id = request.state.tenant_id
    is_admin = request.state.is_admin

    await deactivate_user(
        db,
        actor=current_user,
        target_user_id=user_id,
        current_tenant_id=tenant_id,
        is_admin=is_admin,
        ip_address=request.client.host if request.client else None,
    )
    # Immediately invalidate active access tokens for this user+tenant
    await revoke_tenant_membership(redis, user_id, tenant_id)
    await db.commit()


# --- Admin-only endpoints ---


@router.post("/{user_id}/reset-password", status_code=200, response_model=MessageResponse)
async def admin_reset_password(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin resets a user's password — sends email with reset link."""
    tenant_id = request.state.tenant_id

    token, target = await reset_password(
        db,
        admin=current_user,
        target_user_id=user_id,
        tenant_id=tenant_id,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    try:
        send_password_reset_email_task.delay(target.email, token, target.name)
    except Exception:
        logger.exception("Failed to queue password reset email for %s", target.email)

    return {"message": "E-mail z linkiem do resetu hasła został wysłany"}


@router.post("/{user_id}/block", response_model=UserResponse)
async def admin_block_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin blokuje konto użytkownika (Story 6.15, AC3)."""
    return await _set_blocked(user_id, request, current_user, db, blocked=True)


@router.post("/{user_id}/unblock", response_model=UserResponse)
async def admin_unblock_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin odblokowuje konto użytkownika (Story 6.15, AC3)."""
    return await _set_blocked(user_id, request, current_user, db, blocked=False)


async def _set_blocked(
    user_id: uuid.UUID,
    request: Request,
    current_user: User,
    db: AsyncSession,
    *,
    blocked: bool,
) -> UserResponse:
    tenant_id = request.state.tenant_id
    target = await set_user_blocked(
        db,
        admin=current_user,
        target_user_id=user_id,
        blocked=blocked,
        tenant_id=tenant_id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return _build_user_response(target, tenant_id, request.state.role)


@router.post("/reset-password-token", response_model=MessageResponse)
async def reset_password_by_token(
    body: ResetPasswordByTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Use a password reset token to set a new password (public endpoint)."""
    await use_password_reset_token(db, token=body.token, new_password=body.new_password)
    await db.commit()
    return {"message": "Hasło zostało zresetowane"}
