"""Redis-backed token store for refresh tokens, blacklist, and brute force protection."""

import uuid

from redis.asyncio import Redis

from app.core.config import get_settings


async def store_refresh_token(redis: Redis, jti: str, user_id: uuid.UUID, ttl_seconds: int) -> None:
    await redis.set(f"refresh:{jti}", str(user_id), ex=ttl_seconds)


async def revoke_refresh_token(redis: Redis, jti: str) -> None:
    await redis.delete(f"refresh:{jti}")


async def is_refresh_token_valid(redis: Redis, jti: str) -> bool:
    return await redis.exists(f"refresh:{jti}") == 1


async def blacklist_access_token(redis: Redis, jti: str, remaining_ttl: int) -> None:
    if remaining_ttl > 0:
        await redis.set(f"blacklist:{jti}", "1", ex=remaining_ttl)


async def is_access_token_blacklisted(redis: Redis, jti: str) -> bool:
    return await redis.exists(f"blacklist:{jti}") == 1


async def revoke_tenant_membership(redis: Redis, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Mark a user's tenant membership as revoked. Checked on every request to invalidate
    active access tokens immediately after deactivation."""
    settings = get_settings()
    ttl = settings.jwt_access_token_expire_minutes * 60
    await redis.set(f"tenant_revoked:{user_id}:{tenant_id}", "1", ex=ttl)


async def is_tenant_membership_revoked(redis: Redis, user_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
    return await redis.exists(f"tenant_revoked:{user_id}:{tenant_id}") == 1


async def increment_login_attempts(redis: Redis, user_id: uuid.UUID) -> int:
    settings = get_settings()
    key = f"login_attempts:{user_id}"
    ttl = settings.login_attempts_window_minutes * 60
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, ttl)
    return count


async def get_login_attempts(redis: Redis, user_id: uuid.UUID) -> int:
    val = await redis.get(f"login_attempts:{user_id}")
    return int(val) if val else 0


async def lock_account(redis: Redis, user_id: uuid.UUID) -> None:
    settings = get_settings()
    await redis.set(f"account_locked:{user_id}", "1", ex=settings.account_lockout_minutes * 60)


async def is_account_locked(redis: Redis, user_id: uuid.UUID) -> bool:
    return await redis.exists(f"account_locked:{user_id}") == 1


async def clear_login_attempts(redis: Redis, user_id: uuid.UUID) -> None:
    await redis.delete(f"login_attempts:{user_id}")


async def increment_mfa_attempts(redis: Redis, mfa_jti: str) -> int:
    """Track MFA verification attempts per token. Max 5 attempts in token lifetime."""
    settings = get_settings()
    key = f"mfa_attempts:{mfa_jti}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.mfa_attempts_window_minutes * 60)
    return count


async def get_mfa_attempts(redis: Redis, mfa_jti: str) -> int:
    val = await redis.get(f"mfa_attempts:{mfa_jti}")
    return int(val) if val else 0


async def store_pre_auth_token(redis: Redis, jti: str) -> None:
    await redis.set(f"pre_auth:{jti}", "1", ex=300)


async def is_pre_auth_token_valid(redis: Redis, jti: str) -> bool:
    return await redis.exists(f"pre_auth:{jti}") == 1


async def consume_pre_auth_token(redis: Redis, jti: str) -> None:
    await redis.delete(f"pre_auth:{jti}")
