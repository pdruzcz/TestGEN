"""Authentication service: registration, email verification, user invitation, login, refresh, logout."""

import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import NIL_UUID
from app.core.exceptions import AuthError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import check_needs_rehash, hash_password, verify_password
from app.core.slugify import slugify
from app.models.email_verification import EmailVerification, VerificationType
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant
from app.services.admin.audit_service import log_action
from app.services.auth import token_store
from app.services.auth.jwt_handler import (
    create_access_token,
    create_mfa_token,
    create_pre_auth_token,
    create_refresh_token,
    decode_token,
)

logger = logging.getLogger(__name__)


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


async def register(
    db: AsyncSession,
    email: str,
    password: str,
    company_name: str,
    nip: str | None = None,
) -> tuple[User, str]:
    """Register new tenant + owner user. Returns (user, verification_token).

    Email is unique globally. If email already exists, user must register via invite flow.
    """
    await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

    _validate_password(password)

    email = email.lower().strip()

    # Email must be globally unique
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ConflictError("Email already registered", field="email")

    if nip:
        existing_tenant = await db.execute(select(Tenant).where(Tenant.nip == nip))
        if existing_tenant.scalar_one_or_none():
            raise ConflictError("NIP already registered", field="nip")

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=email.split("@")[0],
        is_admin=False,
        is_active=False,
    )
    db.add(user)
    await db.flush()

    tenant = Tenant(name=company_name, slug=slugify(company_name), nip=nip)
    db.add(tenant)
    await db.flush()

    user_tenant = UserTenant(
        user_id=user.id,
        tenant_id=tenant.id,
        role=TenantRole.OWNER,
    )
    db.add(user_tenant)
    await db.flush()

    # Story 7.1/AC2 — nowy tenant dostaje automatycznie subskrypcję Freemium
    # (bez danych płatnościowych). Non-fatal: rejestracja nie może paść
    # przez niedostępny moduł billingowy (seed planów w startupie).
    try:
        from app.services.billing.subscription_service import SubscriptionService

        await SubscriptionService(db).create_freemium_subscription(tenant.id)
    except Exception:
        logger.exception("Failed to create freemium subscription for tenant %s", tenant.id)

    token = secrets.token_hex(32)
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        type=VerificationType.REGISTRATION,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(verification)
    await db.flush()

    await log_action(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=user.id,
    )

    return user, token


async def verify_email(db: AsyncSession, token: str) -> User:
    """Verify email and activate user account."""
    await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

    result = await db.execute(
        select(EmailVerification)
        .where(
            EmailVerification.token == token,
            EmailVerification.type == VerificationType.REGISTRATION,
        )
        .with_for_update()
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise NotFoundError("Invalid verification token")

    if verification.used_at is not None:
        raise ValidationError("Token already used")

    if verification.expires_at < datetime.now(UTC):
        raise ValidationError("Token expired")

    verification.used_at = datetime.now(UTC)

    result = await db.execute(select(User).where(User.id == verification.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.is_active = True
    user.email_verified_at = datetime.now(UTC)

    # Get tenant_id from user_tenants for audit log
    ut_result = await db.execute(select(UserTenant).where(UserTenant.user_id == user.id))
    user_tenant = ut_result.scalars().first()

    await log_action(
        db,
        tenant_id=user_tenant.tenant_id if user_tenant else NIL_UUID,
        user_id=user.id,
        action="user.email_verified",
        resource_type="user",
        resource_id=user.id,
    )

    return user


async def accept_invitation(
    db: AsyncSession,
    token: str,
    password: str,
) -> User:
    """Accept invitation: set password and activate user account."""
    await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

    _validate_password(password)

    result = await db.execute(
        select(EmailVerification)
        .where(
            EmailVerification.token == token,
            EmailVerification.type == VerificationType.INVITATION,
        )
        .with_for_update()
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise NotFoundError("Invalid invitation token")

    if verification.used_at is not None:
        raise ValidationError("Token already used")

    if verification.expires_at < datetime.now(UTC):
        raise ValidationError("Token expired")

    verification.used_at = datetime.now(UTC)

    result = await db.execute(select(User).where(User.id == verification.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")

    user.password_hash = hash_password(password)
    user.is_active = True
    user.email_verified_at = datetime.now(UTC)

    # Get tenant_id from user_tenants for audit log
    ut_result = await db.execute(select(UserTenant).where(UserTenant.user_id == user.id))
    user_tenant = ut_result.scalars().first()

    await log_action(
        db,
        tenant_id=user_tenant.tenant_id if user_tenant else NIL_UUID,
        user_id=user.id,
        action="user.invitation_accepted",
        resource_type="user",
        resource_id=user.id,
    )

    return user


async def invite_user(
    db: AsyncSession,
    owner: User,
    owner_tenant_id: uuid.UUID,
    owner_role: str,
    email: str,
    role: TenantRole = TenantRole.USER,
) -> tuple[User, str | None]:
    """Invite a user to a tenant. Returns (user, invitation_token_or_none).

    If email already registered: creates UserTenant only, sends notification.
    If email new: creates User (inactive) + UserTenant + EmailVerification, sends invitation.
    """
    if owner_role not in ("owner", "admin") and not owner.is_admin:
        raise ValidationError("Only owners and admins can invite users")

    if role == TenantRole.OWNER and owner_role != "admin" and not owner.is_admin:
        raise ForbiddenError("Only admins can assign the owner role")

    email = email.lower().strip()

    if email == (owner.email or "").lower().strip():
        raise ValidationError("Cannot invite yourself")

    # Set RLS context for UserTenant writes
    await db.execute(text(f"SET LOCAL app.current_tenant = '{owner_tenant_id}'"))

    # Check if user already in this tenant
    existing_user = await db.execute(select(User).where(User.email == email))
    user = existing_user.scalar_one_or_none()

    if user:
        # Existing user — must be active to join new tenant
        if not user.is_active:
            raise ValidationError("Cannot invite inactive user")

        # Existing user — check if already in this tenant
        existing_ut = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == user.id,
                UserTenant.tenant_id == owner_tenant_id,
            )
        )
        if existing_ut.scalar_one_or_none():
            raise ConflictError("User already exists in this tenant")

        # Add existing user to tenant
        user_tenant = UserTenant(
            user_id=user.id,
            tenant_id=owner_tenant_id,
            role=role,
            invited_by=owner.id,
        )
        db.add(user_tenant)
        await db.flush()

        await log_action(
            db,
            tenant_id=owner_tenant_id,
            user_id=owner.id,
            action="user.invited",
            resource_type="user",
            resource_id=user.id,
        )

        # No token needed — user already has a password
        return user, None

    # New user — create User (inactive) + UserTenant + invitation token
    user = User(
        email=email,
        password_hash="!INVITATION_PENDING!",
        name=email.split("@")[0],
        is_admin=False,
        is_active=False,
    )
    db.add(user)
    await db.flush()

    user_tenant = UserTenant(
        user_id=user.id,
        tenant_id=owner_tenant_id,
        role=role,
        invited_by=owner.id,
    )
    db.add(user_tenant)
    await db.flush()

    token = secrets.token_hex(32)
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        type=VerificationType.INVITATION,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(verification)
    await db.flush()

    await log_action(
        db,
        tenant_id=owner_tenant_id,
        user_id=owner.id,
        action="user.invited",
        resource_type="user",
        resource_id=user.id,
    )

    return user, token


class LoginResult:
    """Result of a login attempt."""

    def __init__(
        self,
        *,
        mfa_required: bool = False,
        mfa_token: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        tenants_required: bool = False,
        pre_auth_token: str | None = None,
        tenants: list[dict] | None = None,
    ):
        self.mfa_required = mfa_required
        self.mfa_token = mfa_token
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.tenants_required = tenants_required
        self.pre_auth_token = pre_auth_token
        self.tenants = tenants


class AccountLockedError(AuthError):
    status_code = 429
    error_type = "account-locked"
    title = "Too Many Requests"


async def login(
    db: AsyncSession,
    redis: Redis,
    email: str,
    password: str,
    ip_address: str | None = None,
) -> LoginResult:
    """Authenticate user with email/password. Returns tokens, MFA challenge, or tenant list."""
    settings = get_settings()
    await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

    email = email.lower().strip()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise AuthError("Invalid credentials")

    if await token_store.is_account_locked(redis, user.id):
        raise AccountLockedError(
            "Account temporarily locked due to too many failed login attempts",
            retry_after=settings.account_lockout_minutes * 60,
        )

    # Story 6.15 (AC3): is_blocked to odwracalna blokada logowania nałożona
    # przez admina — ten sam komunikat co dla złych danych (bez enumeracji kont)
    if not user.is_active or user.is_blocked:
        raise AuthError("Invalid credentials")

    if not verify_password(password, user.password_hash):
        attempts = await token_store.increment_login_attempts(redis, user.id)
        if attempts >= settings.max_login_attempts:
            await token_store.lock_account(redis, user.id)

        await log_action(
            db,
            tenant_id=NIL_UUID,
            user_id=user.id,
            action="user.login_failed",
            resource_type="user",
            resource_id=user.id,
            ip_address=ip_address,
        )
        raise AuthError("Invalid credentials")

    # Rehash if needed
    if check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    await token_store.clear_login_attempts(redis, user.id)

    # Get user's tenants via user_tenants
    ut_result = await db.execute(select(UserTenant).where(UserTenant.user_id == user.id))
    user_tenants = list(ut_result.scalars().all())

    if not user_tenants:
        raise AuthError("User has no tenant assignments")

    # Platform admin — get all accessible tenants
    if user.is_admin:
        tenants_result = await db.execute(select(Tenant))
        all_tenants = {t.id: t for t in tenants_result.scalars().all()}

        tenant_infos = [
            {
                "tenant_id": tid,
                "tenant_name": all_tenants[tid].name if tid in all_tenants else "Unknown",
                "role": "admin",
            }
            for tid in all_tenants
        ]

        if len(tenant_infos) == 1:
            tid = tenant_infos[0]["tenant_id"]

            # H1 fix: Check MFA for admin single-tenant (was bypassed)
            from app.models.mfa import UserMFA

            mfa_result = await db.execute(
                select(UserMFA).where(UserMFA.user_id == user.id, UserMFA.is_enabled.is_(True))
            )
            mfa_record = mfa_result.scalar_one_or_none()
            if mfa_record:
                mfa_token = create_mfa_token(user.id, tid, "admin", is_admin=True)
                return LoginResult(mfa_required=True, mfa_token=mfa_token)

            access_token = create_access_token(user.id, tid, "admin", is_admin=True)
            refresh_token = create_refresh_token(user.id)
            refresh_payload = decode_token(refresh_token)
            await token_store.store_refresh_token(
                redis,
                refresh_payload["jti"],
                user.id,
                settings.jwt_refresh_token_expire_days * 86400,
            )

            await log_action(
                db,
                tenant_id=tid,
                user_id=user.id,
                action="user.login_success",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip_address,
            )

            return LoginResult(access_token=access_token, refresh_token=refresh_token)

        tenant_id_strs = [str(t["tenant_id"]) for t in tenant_infos]
        pre_auth_token = create_pre_auth_token(email, tenant_id_strs)
        pre_payload = decode_token(pre_auth_token)
        await token_store.store_pre_auth_token(redis, pre_payload["jti"])

        return LoginResult(
            tenants_required=True,
            pre_auth_token=pre_auth_token,
            tenants=tenant_infos,
        )

    # Regular user — get tenants from user_tenants
    tenant_ids = [ut.tenant_id for ut in user_tenants]
    tenants_result = await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))
    tenant_map = {t.id: t for t in tenants_result.scalars().all()}

    tenant_infos = []
    for ut in user_tenants:
        tenant = tenant_map.get(ut.tenant_id)
        if tenant:
            tenant_infos.append(
                {
                    "tenant_id": ut.tenant_id,
                    "tenant_name": tenant.name,
                    "role": ut.role.value,
                }
            )

    if not tenant_infos:
        raise AuthError("User has no valid tenant assignments")

    # Single tenant — backward compatible
    if len(tenant_infos) == 1:
        ti = tenant_infos[0]

        from app.models.mfa import UserMFA

        mfa_result = await db.execute(select(UserMFA).where(UserMFA.user_id == user.id, UserMFA.is_enabled.is_(True)))
        mfa_record = mfa_result.scalar_one_or_none()
        if mfa_record:
            mfa_token = create_mfa_token(user.id, ti["tenant_id"], ti["role"])
            return LoginResult(mfa_required=True, mfa_token=mfa_token)

        access_token = create_access_token(user.id, ti["tenant_id"], ti["role"], is_admin=False)
        refresh_token = create_refresh_token(user.id)
        refresh_payload = decode_token(refresh_token)
        await token_store.store_refresh_token(
            redis,
            refresh_payload["jti"],
            user.id,
            settings.jwt_refresh_token_expire_days * 86400,
        )

        await log_action(
            db,
            tenant_id=ti["tenant_id"],
            user_id=user.id,
            action="user.login_success",
            resource_type="user",
            resource_id=user.id,
            ip_address=ip_address,
        )

        return LoginResult(access_token=access_token, refresh_token=refresh_token)

    # Multiple tenants — return tenant picker
    tenant_id_strs = [str(t["tenant_id"]) for t in tenant_infos]
    pre_auth_token = create_pre_auth_token(email, tenant_id_strs)
    pre_payload = decode_token(pre_auth_token)
    await token_store.store_pre_auth_token(redis, pre_payload["jti"])

    return LoginResult(
        tenants_required=True,
        pre_auth_token=pre_auth_token,
        tenants=tenant_infos,
    )


async def select_tenant(
    db: AsyncSession,
    redis: Redis,
    pre_auth_token: str,
    tenant_id: uuid.UUID,
    ip_address: str | None = None,
) -> LoginResult:
    """Complete login by selecting a tenant. Returns tokens or MFA challenge."""
    settings = get_settings()
    await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

    try:
        payload = decode_token(pre_auth_token)
    except Exception as exc:
        raise AuthError("Invalid or expired pre-authentication token") from exc

    if payload.get("type") != "pre_auth":
        raise AuthError("Invalid token type")

    jti = payload.get("jti")
    if not jti or not await token_store.is_pre_auth_token_valid(redis, jti):
        raise AuthError("Pre-authentication token expired or already used")

    email = payload.get("sub")
    allowed_tenants = payload.get("tenant_ids", [])

    if str(tenant_id) not in allowed_tenants:
        raise AuthError("Invalid tenant selection")

    await token_store.consume_pre_auth_token(redis, jti)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or user.is_blocked:
        raise AuthError("User not found or inactive")

    # Get role from user_tenants
    ut_result = await db.execute(
        select(UserTenant).where(
            UserTenant.user_id == user.id,
            UserTenant.tenant_id == tenant_id,
        )
    )
    user_tenant = ut_result.scalar_one_or_none()

    role = "admin" if user.is_admin else (user_tenant.role.value if user_tenant else "user")

    from app.models.mfa import UserMFA

    mfa_result = await db.execute(select(UserMFA).where(UserMFA.user_id == user.id, UserMFA.is_enabled.is_(True)))
    mfa_record = mfa_result.scalar_one_or_none()
    if mfa_record:
        mfa_token = create_mfa_token(user.id, tenant_id, role, is_admin=user.is_admin)
        return LoginResult(mfa_required=True, mfa_token=mfa_token)

    access_token = create_access_token(user.id, tenant_id, role, is_admin=user.is_admin)
    refresh_token = create_refresh_token(user.id)
    refresh_payload = decode_token(refresh_token)
    await token_store.store_refresh_token(
        redis,
        refresh_payload["jti"],
        user.id,
        settings.jwt_refresh_token_expire_days * 86400,
    )

    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="user.login_success",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
    )

    return LoginResult(access_token=access_token, refresh_token=refresh_token)


async def refresh_tokens(
    db: AsyncSession,
    redis: Redis,
    refresh_cookie: str,
) -> tuple[str, str]:
    """Rotate refresh token and issue new access token. Returns (access_token, refresh_token)."""
    settings = get_settings()
    await db.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

    try:
        payload = decode_token(refresh_cookie)
    except Exception as exc:
        raise AuthError("Invalid or expired refresh token") from exc

    if payload.get("type") != "refresh":
        raise AuthError("Invalid token type")

    jti = payload.get("jti")
    if not jti or not await token_store.is_refresh_token_valid(redis, jti):
        raise AuthError("Refresh token revoked or invalid")

    await token_store.revoke_refresh_token(redis, jti)

    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Invalid token payload")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or user.is_blocked:
        raise AuthError("User not found or inactive")

    # Get first tenant for refresh token (user should re-login for tenant switch)
    # Always re-validate role from user_tenants — prevents stale-role privilege persistence
    old_tenant_id = payload.get("tenant_id")

    if old_tenant_id:
        tenant_id = uuid.UUID(old_tenant_id)
        ut_result = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == user.id,
                UserTenant.tenant_id == tenant_id,
            )
        )
        current_ut = ut_result.scalar_one_or_none()
        if not current_ut:
            raise AuthError("User no longer has access to this tenant")
        role = "admin" if user.is_admin else current_ut.role.value
    else:
        ut_result = await db.execute(select(UserTenant).where(UserTenant.user_id == user.id))
        first_ut = ut_result.scalars().first()
        if not first_ut:
            raise AuthError("User has no tenant assignments")
        tenant_id = first_ut.tenant_id
        role = "admin" if user.is_admin else first_ut.role.value

    access_token = create_access_token(user.id, tenant_id, role, is_admin=user.is_admin)
    new_refresh_token = create_refresh_token(user.id)
    new_payload = decode_token(new_refresh_token)
    await token_store.store_refresh_token(
        redis,
        new_payload["jti"],
        user.id,
        settings.jwt_refresh_token_expire_days * 86400,
    )

    return access_token, new_refresh_token


async def logout(
    redis: Redis,
    access_token_raw: str | None,
    refresh_token_raw: str | None,
) -> None:
    """Blacklist access token and revoke refresh token."""
    if access_token_raw:
        try:
            payload = decode_token(access_token_raw)
            jti = payload.get("jti")
            exp = payload.get("exp", 0)
            now = int(datetime.now(UTC).timestamp())
            remaining = max(exp - now, 0)
            if jti and remaining > 0:
                await token_store.blacklist_access_token(redis, jti, remaining)
        except Exception:
            pass  # graceful logout — don't fail on invalid tokens

    if refresh_token_raw:
        try:
            payload = decode_token(refresh_token_raw)
            jti = payload.get("jti")
            if jti:
                await token_store.revoke_refresh_token(redis, jti)
        except Exception:
            pass
