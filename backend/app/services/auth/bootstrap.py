"""Bootstrap platform admin on application startup via environment variables."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import NIL_UUID
from app.core.security import hash_password
from app.models.tenant import PlanType, Tenant
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant
from app.services.admin.audit_service import log_action

logger = logging.getLogger(__name__)

SYSTEM_TENANT_NAME = "__system__"


async def bootstrap_admin(db: AsyncSession, settings: Settings) -> None:
    """Create platform admin + system tenant if no admin exists and bootstrap is enabled.

    Idempotent — safe to call on every startup. No-op if an admin already exists
    or if BOOTSTRAP_ADMIN is not enabled.
    """
    if not settings.bootstrap_admin:
        return

    if not settings.admin_email or not settings.admin_password:
        logger.warning("BOOTSTRAP_ADMIN enabled but ADMIN_EMAIL or ADMIN_PASSWORD not set — skipping")
        return

    await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

    # Check if any admin already exists
    result = await db.execute(select(User).where(User.is_admin.is_(True)))
    if result.scalar_one_or_none():
        logger.info("Admin user already exists — bootstrap skipped")
        return

    email = settings.admin_email.lower().strip()

    # Check if admin email already taken by a non-admin user
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        logger.warning("User with admin email %s already exists (non-admin) — bootstrap skipped", email)
        return

    # Create or reuse system tenant
    result = await db.execute(select(Tenant).where(Tenant.name == SYSTEM_TENANT_NAME))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(name=SYSTEM_TENANT_NAME, slug="__system__", plan=PlanType.PREMIUM, is_active=True)
        db.add(tenant)
        await db.flush()
        logger.info("System tenant created (id=%s)", tenant.id)
    else:
        logger.info("System tenant already exists (id=%s)", tenant.id)

    # Create admin user — active and verified immediately
    now = datetime.now(UTC)
    user = User(
        email=email,
        password_hash=hash_password(settings.admin_password),
        name="Platform Admin",
        is_admin=True,
        is_active=True,
        email_verified_at=now,
    )
    db.add(user)
    await db.flush()

    # Create UserTenant for system tenant
    user_tenant = UserTenant(
        user_id=user.id,
        tenant_id=tenant.id,
        role=TenantRole.OWNER,
    )
    db.add(user_tenant)
    await db.flush()

    await log_action(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        action="admin.bootstrapped",
        resource_type="user",
        resource_id=user.id,
    )

    await db.commit()

    logger.info(
        "Platform admin bootstrapped: email=%s, user_id=%s, tenant_id=%s",
        email,
        user.id,
        tenant.id,
    )
