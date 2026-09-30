"""MFA (TOTP) service: setup, confirm, verify, disable, backup codes."""

import secrets
import uuid

import pyotp
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import AuthError, ValidationError
from app.core.security import hash_password, verify_password
from app.models.mfa import UserMFA
from app.models.user import User
from app.services.admin.audit_service import log_action
from app.services.auth import token_store
from app.services.auth.jwt_handler import create_access_token, create_refresh_token, decode_token

_ISSUER_NAME = "TestGEN"


def _generate_backup_codes(count: int = 10, length: int = 8) -> list[str]:
    # Generate alphanumeric codes (a-z, A-Z, 0-9) with sufficient entropy.
    # secrets.choice from a 62-char alphabet gives ~47.6 bits of entropy per code.
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ["".join(secrets.choice(alphabet) for _ in range(length)) for _ in range(count)]


async def setup_mfa(db: AsyncSession, user_id: uuid.UUID, email: str) -> dict:
    """Initialize MFA setup — returns secret and provisioning URI."""
    result = await db.execute(select(UserMFA).where(UserMFA.user_id == user_id))
    existing = result.scalar_one_or_none()
    if existing and existing.is_enabled:
        raise ValidationError("MFA is already enabled")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(email, issuer_name=_ISSUER_NAME)

    encrypted_secret = encrypt(secret)
    if existing:
        existing.totp_secret = encrypted_secret
        existing.is_enabled = False
    else:
        mfa = UserMFA(user_id=user_id, totp_secret=encrypted_secret, is_enabled=False)
        db.add(mfa)

    await db.flush()
    return {"secret": secret, "provisioning_uri": provisioning_uri}


async def confirm_mfa(db: AsyncSession, user_id: uuid.UUID, code: str) -> list[str]:
    """Confirm MFA setup with TOTP code. Returns plain-text backup codes (shown once)."""
    result = await db.execute(select(UserMFA).where(UserMFA.user_id == user_id))
    mfa = result.scalar_one_or_none()
    if not mfa:
        raise ValidationError("MFA setup not initiated")
    if mfa.is_enabled:
        raise ValidationError("MFA is already enabled")

    totp = pyotp.TOTP(decrypt(mfa.totp_secret))
    if not totp.verify(code, valid_window=1):
        raise ValidationError("Invalid TOTP code")

    backup_codes = _generate_backup_codes()
    mfa.backup_codes_hash = [hash_password(c) for c in backup_codes]
    mfa.is_enabled = True
    await db.flush()
    return backup_codes


async def verify_mfa_login(
    db: AsyncSession,
    redis: Redis,
    mfa_token: str,
    code: str,
    ip_address: str | None = None,
) -> tuple[str, str]:
    """Verify TOTP or backup code after MFA challenge. Returns (access_token, refresh_token)."""
    settings = get_settings()

    try:
        payload = decode_token(mfa_token)
    except Exception as exc:
        raise AuthError("Invalid or expired MFA token") from exc

    if payload.get("type") != "mfa":
        raise AuthError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Invalid MFA token payload")

    uid = uuid.UUID(user_id)
    result = await db.execute(select(UserMFA).where(UserMFA.user_id == uid))
    mfa = result.scalar_one_or_none()
    if not mfa or not mfa.is_enabled:
        raise AuthError("MFA not configured")

    # Replay protection: reject previously-used TOTP codes within validity window
    replay_key = f"totp_used:{uid}:{code}"
    if await redis.exists(replay_key):
        raise AuthError("TOTP code already used")

    # Try TOTP first
    totp = pyotp.TOTP(decrypt(mfa.totp_secret))
    verified = totp.verify(code, valid_window=1)
    if verified:
        # Mark code as used for 90s (valid_window=1 -> 3 steps * 30s)
        await redis.setex(replay_key, 90, "1")

    # Try backup code if TOTP fails.
    # O(n) Argon2id comparisons (max 10 codes * ~100ms). Accepted trade-off:
    # backup code usage is rare, and rate limiting (5 attempts/token) bounds total cost.
    if not verified:
        for i, hashed in enumerate(mfa.backup_codes_hash):
            if verify_password(code, hashed):
                # Mark backup code as used by removing it
                codes = list(mfa.backup_codes_hash)
                codes.pop(i)
                mfa.backup_codes_hash = codes
                verified = True
                break

    if not verified:
        raise AuthError("Invalid TOTP or backup code")

    # Issue tokens
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthError("User not found or inactive")

    # H2 fix: Use tenant_id and role from MFA token if present (select-tenant flow).
    # Falls back to first UserTenant for backward compatibility.
    tenant_id_claim = payload.get("tenant_id")
    role_claim = payload.get("role")
    is_admin_claim = payload.get("is_admin", False)

    if tenant_id_claim and role_claim:
        tenant_id = uuid.UUID(tenant_id_claim)
        role = role_claim
    else:
        from app.models.user_tenant import UserTenant

        ut_result = await db.execute(select(UserTenant).where(UserTenant.user_id == user.id))
        user_tenant = ut_result.scalars().first()
        if not user_tenant:
            raise AuthError("User has no tenant assignments")
        tenant_id = user_tenant.tenant_id
        role = "admin" if user.is_admin else user_tenant.role.value

    access_token = create_access_token(user.id, tenant_id, role, is_admin=is_admin_claim or user.is_admin)
    refresh_token = create_refresh_token(user.id)
    refresh_payload = decode_token(refresh_token)
    await token_store.store_refresh_token(
        redis,
        refresh_payload["jti"],
        user.id,
        settings.jwt_refresh_token_expire_days * 86400,
    )

    # M1 fix: Include ip_address in MFA login audit log
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="user.login_success",
        resource_type="user",
        resource_id=user.id,
        changes={"mfa": True},
        ip_address=ip_address,
    )

    await db.flush()
    return access_token, refresh_token


async def disable_mfa(db: AsyncSession, user_id: uuid.UUID, password: str) -> None:
    """Disable MFA — requires password confirmation."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthError("User not found")

    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid password")

    result = await db.execute(select(UserMFA).where(UserMFA.user_id == user_id))
    mfa = result.scalar_one_or_none()
    if not mfa or not mfa.is_enabled:
        raise ValidationError("MFA is not enabled")

    await db.delete(mfa)
    await db.flush()


async def regenerate_backup_codes(db: AsyncSession, user_id: uuid.UUID, password: str) -> list[str]:
    """Regenerate backup codes — requires password confirmation."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthError("User not found")

    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid password")

    result = await db.execute(select(UserMFA).where(UserMFA.user_id == user_id))
    mfa = result.scalar_one_or_none()
    if not mfa or not mfa.is_enabled:
        raise ValidationError("MFA is not enabled")

    backup_codes = _generate_backup_codes()
    mfa.backup_codes_hash = [hash_password(c) for c in backup_codes]
    await db.flush()
    return backup_codes
