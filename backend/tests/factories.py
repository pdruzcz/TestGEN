"""Test factories for creating model instances."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from app.core.security import hash_password
from app.models.email_verification import EmailVerification, VerificationType
from app.models.tenant import PlanType, Tenant
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant

# Cache the default password hash to avoid slow Argon2id computation per test
_DEFAULT_PASSWORD = "SecurePassword123!"


@lru_cache
def _default_password_hash() -> str:
    return hash_password(_DEFAULT_PASSWORD)


def make_tenant(
    name: str = "Test Company",
    slug: str | None = None,
    nip: str | None = None,
    plan: PlanType = PlanType.FREEMIUM,
    is_active: bool = True,
) -> Tenant:
    return Tenant(
        id=uuid.uuid4(),
        name=name,
        slug=slug or name.lower().replace(" ", "-"),
        nip=nip,
        plan=plan,
        is_active=is_active,
    )


def make_user(
    email: str = "user@test.com",
    password: str = _DEFAULT_PASSWORD,
    name: str = "Test User",
    is_admin: bool = False,
    is_active: bool = True,
) -> User:
    pw_hash = _default_password_hash() if password == _DEFAULT_PASSWORD else hash_password(password)
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash=pw_hash,
        name=name,
        is_admin=is_admin,
        is_active=is_active,
        email_verified_at=datetime.now(UTC) if is_active else None,
        notification_preferences={},
    )


def make_user_tenant(
    user_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    role: TenantRole = TenantRole.USER,
    invited_by: uuid.UUID | None = None,
) -> UserTenant:
    return UserTenant(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        role=role,
        invited_by=invited_by,
    )


def make_verification(
    user_id: uuid.UUID | None = None,
    token: str | None = None,
    vtype: VerificationType = VerificationType.REGISTRATION,
    hours_valid: int = 24,
    used: bool = False,
) -> EmailVerification:
    return EmailVerification(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        token=token or secrets.token_hex(32),
        type=vtype,
        expires_at=datetime.now(UTC) + timedelta(hours=hours_valid),
        used_at=datetime.now(UTC) if used else None,
    )
