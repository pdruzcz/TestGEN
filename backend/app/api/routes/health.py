from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_engine

router = APIRouter()


async def _check_db() -> str:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "unavailable"


async def _check_redis() -> str:
    settings = get_settings()
    try:
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        return "ok"
    except Exception:
        return "unavailable"


async def _check_rabbitmq() -> str:
    import asyncio

    settings = get_settings()
    try:
        # Simple TCP check for RabbitMQ
        parts = settings.rabbitmq_url.replace("amqp://", "").split("@")
        host_port = parts[1].rstrip("/").split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 5672
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2)
        writer.close()
        await writer.wait_closed()
        return "ok"
    except Exception:
        return "unavailable"


@router.get("/health")
async def health_check(response: Response) -> dict[str, Any]:
    db_status = await _check_db()
    redis_status = await _check_redis()
    rabbitmq_status = await _check_rabbitmq()

    dependencies = {
        "database": db_status,
        "redis": redis_status,
        "rabbitmq": rabbitmq_status,
    }

    all_ok = all(s == "ok" for s in dependencies.values())

    if not all_ok:
        response.status_code = 503

    return {
        "status": "ok" if all_ok else "degraded",
        "dependencies": dependencies,
    }


@router.get("/config")
async def get_public_config() -> dict[str, str]:
    """Publiczna konfiguracja systemu (nie wymaga autoryzacji)."""
    settings = get_settings()
    return {"engine_mode": settings.engine_mode.value}


@router.get("/readiness")
async def readiness_check(response: Response) -> dict[str, Any]:
    return await health_check(response)
