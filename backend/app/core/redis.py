"""Async Redis client singleton for token store, rate limiting, and session management."""

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool.from_url(settings.redis_url, max_connections=20, decode_responses=True)
    return _pool


async def get_redis() -> Redis:
    return Redis(connection_pool=_get_pool())


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
