"""RS256 JWT token creation and validation."""

import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import jwt

from app.core.config import get_settings

_JWT_ISSUER = "testgen"
_JWT_AUDIENCE = "testgen"


@lru_cache
def _read_key(path: Path) -> str:
    """Read and cache PEM key file. Cache is intentionally permanent per process —
    JWT key rotation requires process restart (standard RS256 key management)."""
    return path.read_text()


def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str, *, is_admin: bool = False) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "is_admin": is_admin,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
    }
    private_key = _read_key(settings.jwt_private_key_path)
    return jwt.encode(payload, private_key, algorithm="RS256")


def create_refresh_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
    }
    private_key = _read_key(settings.jwt_private_key_path)
    return jwt.encode(payload, private_key, algorithm="RS256")


def create_mfa_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
    role: str | None = None,
    *,
    is_admin: bool = False,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.mfa_token_expire_minutes),
        "type": "mfa",
        "jti": str(uuid.uuid4()),
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
    }
    if tenant_id is not None:
        payload["tenant_id"] = str(tenant_id)
    if role is not None:
        payload["role"] = role
    if is_admin:
        payload["is_admin"] = True
    private_key = _read_key(settings.jwt_private_key_path)
    return jwt.encode(payload, private_key, algorithm="RS256")


def create_pre_auth_token(email: str, tenant_ids: list[str]) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": email,
        "tenant_ids": tenant_ids,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "type": "pre_auth",
        "jti": str(uuid.uuid4()),
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
    }
    private_key = _read_key(settings.jwt_private_key_path)
    return jwt.encode(payload, private_key, algorithm="RS256")


def decode_token(token: str) -> dict:
    settings = get_settings()
    public_key = _read_key(settings.jwt_public_key_path)
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        issuer=_JWT_ISSUER,
        audience=_JWT_AUDIENCE,
    )
