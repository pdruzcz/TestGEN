"""User management service: profile, password, roles."""

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NIL_UUID
from app.core.exceptions import AuthError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import hash_password, verify_password
from app.models.email_verification import EmailVerification, VerificationType
from app.models.tenant import PlanType, Tenant
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant
from app.services.admin.audit_service import log_action


def _validate_password(password: str) -> None:
    """Service-level password validation (defense in depth — schema also validates)."""
    if len(password) < 12:
        raise ValidationError("Password must be at least 12 characters")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValidationError("Password must contain at least one special character")


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return user


async def update_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    name: str | None = None,
    notification_preferences: dict | None = None,
    ip_address: str | None = None,
) -> User:
    user = await get_profile(db, user_id)
    changes: dict = {}
    if name is not None and name != user.name:
        changes["name"] = {"old": user.name, "new": name}
        user.name = name
    if notification_preferences is not None:
        changes["notification_preferences"] = {"old": user.notification_preferences, "new": notification_preferences}
        user.notification_preferences = notification_preferences

    if changes:
        await log_action(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="user.profile_updated",
            resource_type="user",
            resource_id=user.id,
            changes=changes,
            ip_address=ip_address,
        )

    return user


async def change_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    old_password: str,
    new_password: str,
    ip_address: str | None = None,
) -> User:
    _validate_password(new_password)

    user = await get_profile(db, user_id)
    if not verify_password(old_password, user.password_hash):
        raise AuthError("Current password is incorrect")

    if old_password == new_password:
        raise ValidationError("New password must be different from current password")

    user.password_hash = hash_password(new_password)

    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="user.password_changed",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
    )

    return user


async def change_role(
    db: AsyncSession,
    actor: User,
    target_user_id: uuid.UUID,
    new_role: TenantRole,
    current_tenant_id: uuid.UUID,
    is_admin: bool = False,
    ip_address: str | None = None,
) -> User:
    if not is_admin:
        # Check if actor is owner in current tenant
        actor_ut_result = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == actor.id,
                UserTenant.tenant_id == current_tenant_id,
            )
        )
        actor_ut = actor_ut_result.scalar_one_or_none()
        if not actor_ut or actor_ut.role != TenantRole.OWNER:
            raise ForbiddenError("Only owners and admins can change roles")

    result = await db.execute(select(User).where(User.id == target_user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError("User not found")

    if target.id == actor.id:
        raise ForbiddenError("Cannot change your own role")

    # Get target's UserTenant in current tenant
    target_ut_result = await db.execute(
        select(UserTenant).where(
            UserTenant.user_id == target.id,
            UserTenant.tenant_id == current_tenant_id,
        )
    )
    target_ut = target_ut_result.scalar_one_or_none()
    if not target_ut:
        raise NotFoundError("User is not a member of this tenant")

    # Prevent removing the last owner from tenant
    if target_ut.role == TenantRole.OWNER and new_role != TenantRole.OWNER:
        count_result = await db.execute(
            select(UserTenant)
            .where(
                UserTenant.tenant_id == current_tenant_id,
                UserTenant.role == TenantRole.OWNER,
                UserTenant.user_id != target.id,
            )
            .with_for_update()
        )
        if not count_result.scalars().first():
            raise ForbiddenError("Cannot remove the last owner from this tenant")

    old_role = target_ut.role
    target_ut.role = new_role

    await log_action(
        db,
        tenant_id=current_tenant_id,
        user_id=actor.id,
        action="user.role_changed",
        resource_type="user",
        resource_id=target.id,
        changes={"old_role": old_role.value, "new_role": new_role.value},
        ip_address=ip_address,
    )

    return target


async def reset_password(
    db: AsyncSession,
    admin: User,
    target_user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    ip_address: str | None = None,
) -> tuple[str, User]:
    """Admin resets user password — generates token for user to set new password."""
    if not admin.is_admin:
        raise ForbiddenError("Only admins can reset passwords")

    result = await db.execute(select(User).where(User.id == target_user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError("User not found")

    token = secrets.token_hex(32)
    verification = EmailVerification(
        user_id=target.id,
        token=token,
        type=VerificationType.PASSWORD_RESET,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(verification)

    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=admin.id,
        action="user.password_reset",
        resource_type="user",
        resource_id=target.id,
        ip_address=ip_address,
    )

    return token, target


async def deactivate_user(
    db: AsyncSession,
    actor: User,
    target_user_id: uuid.UUID,
    current_tenant_id: uuid.UUID,
    is_admin: bool = False,
    ip_address: str | None = None,
) -> User:
    if not is_admin:
        actor_ut_result = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == actor.id,
                UserTenant.tenant_id == current_tenant_id,
            )
        )
        actor_ut = actor_ut_result.scalar_one_or_none()
        if not actor_ut or actor_ut.role != TenantRole.OWNER:
            raise ForbiddenError("Only owners and admins can deactivate users")

    result = await db.execute(select(User).where(User.id == target_user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError("User not found")

    if target.id == actor.id:
        raise ForbiddenError("Cannot deactivate your own account")

    # Get target's UserTenant in current tenant
    target_ut_result = await db.execute(
        select(UserTenant).where(
            UserTenant.user_id == target.id,
            UserTenant.tenant_id == current_tenant_id,
        )
    )
    target_ut = target_ut_result.scalar_one_or_none()
    if not target_ut:
        raise NotFoundError("User is not a member of this tenant")

    # Prevent deactivating the last owner
    if target_ut.role == TenantRole.OWNER:
        count_result = await db.execute(
            select(UserTenant)
            .where(
                UserTenant.tenant_id == current_tenant_id,
                UserTenant.role == TenantRole.OWNER,
                UserTenant.user_id != target.id,
            )
            .with_for_update()
        )
        if not count_result.scalars().first():
            raise ForbiddenError("Cannot deactivate the last owner from this tenant")

    # Remove user from tenant (soft deactivation per tenant)
    await db.delete(target_ut)

    # Admin platformy usuwa konto globalnie — miękkie usunięcie (Story 6.15, AC3).
    # Właściciel tenanta odbiera tylko dostęp do swojego tenanta.
    if is_admin:
        target.deleted_at = datetime.now(UTC)
        target.is_active = False

    await log_action(
        db,
        tenant_id=current_tenant_id,
        user_id=actor.id,
        action="user.deactivated",
        resource_type="user",
        resource_id=target.id,
        ip_address=ip_address,
    )

    return target


async def set_user_blocked(
    db: AsyncSession,
    *,
    admin: User,
    target_user_id: uuid.UUID,
    blocked: bool,
    tenant_id: uuid.UUID,
    ip_address: str | None = None,
) -> User:
    """Admin blokuje lub odblokowuje konto użytkownika (Story 6.15, AC3).

    Blokada jest odwracalna i niezależna od ``is_active`` (konto nieaktywowane)
    oraz ``deleted_at`` (miękkie usunięcie).
    """
    if not admin.is_admin:
        raise ForbiddenError("Only admins can block users")

    result = await db.execute(select(User).where(User.id == target_user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError("User not found")

    if target.id == admin.id:
        raise ForbiddenError("Cannot block your own account")

    if bool(target.is_blocked) == blocked:
        return target  # brak zmiany — bez wpisu w logu audytu

    target.is_blocked = blocked

    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=admin.id,
        action="user.blocked" if blocked else "user.unblocked",
        resource_type="user",
        resource_id=target.id,
        changes={"old_blocked": not blocked, "new_blocked": blocked},
        ip_address=ip_address,
    )

    return target


async def change_plan(
    db: AsyncSession,
    admin: User,
    tenant_id: uuid.UUID,
    new_plan: PlanType,
    ip_address: str | None = None,
) -> Tenant:
    """Admin changes a tenant's subscription plan."""
    if not admin.is_admin:
        raise ForbiddenError("Only admins can change subscription plans")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError("Tenant not found")

    if not tenant.is_active:
        raise ValidationError("Cannot change plan for a deactivated tenant")

    old_plan = tenant.plan
    if old_plan == new_plan:
        return tenant  # No change needed, skip audit log

    tenant.plan = new_plan

    await log_action(
        db,
        tenant_id=tenant.id,
        user_id=admin.id,
        action="tenant.plan_changed",
        resource_type="tenant",
        resource_id=tenant.id,
        changes={"old_plan": old_plan.value, "new_plan": new_plan.value},
        ip_address=ip_address,
    )

    return tenant


async def use_password_reset_token(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> User:
    """Use a password reset token to set a new password."""
    await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

    _validate_password(new_password)

    result = await db.execute(
        select(EmailVerification)
        .where(
            EmailVerification.token == token,
            EmailVerification.type == VerificationType.PASSWORD_RESET,
        )
        .with_for_update()
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise NotFoundError("Invalid reset token")

    if verification.used_at is not None:
        raise ValidationError("Token already used")

    if verification.expires_at < datetime.now(UTC):
        raise ValidationError("Token expired")

    verification.used_at = datetime.now(UTC)

    result = await db.execute(select(User).where(User.id == verification.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.password_hash = hash_password(new_password)

    # Get tenant for audit log
    ut_result = await db.execute(select(UserTenant).where(UserTenant.user_id == user.id))
    user_tenant = ut_result.scalars().first()

    await log_action(
        db,
        tenant_id=user_tenant.tenant_id if user_tenant else NIL_UUID,
        user_id=user.id,
        action="user.password_reset_completed",
        resource_type="user",
        resource_id=user.id,
    )

    return user
