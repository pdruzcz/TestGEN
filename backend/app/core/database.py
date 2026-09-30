import contextlib
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.constants import NIL_UUID

# ── Async (FastAPI) ──────────────────────────────────────────────────────────

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazy-initialized async engine — avoids module-level side effects at import time."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazy-initialized async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextlib.asynccontextmanager
async def task_session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh async engine+session for ONE Celery task, then disposed.

    Celery tasks run via ``asyncio.run()`` (a fresh event loop per call), but
    the module-level engine from ``get_session_factory()`` binds its asyncpg
    connections to the first loop it ran on. Reusing that engine from a later
    loop raises ``RuntimeError: ... Future ... attached to a different loop``.
    This helper creates a private engine per call so Celery tasks are
    loop-safe. Use only in workers; FastAPI requests keep using ``get_db`` /
    ``get_session_factory`` (they share one stable loop).
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


# ── Sync (Celery workers) ────────────────────────────────────────────────────

_sync_engine = None
_sync_session_factory: sessionmaker[Session] | None = None


def get_sync_engine():
    """Lazy-initialized sync engine for Celery workers."""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        sync_url = settings.database_url.replace("+asyncpg", "+psycopg")
        _sync_engine = create_engine(
            sync_url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    """Lazy-initialized sync session factory for Celery workers."""
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=get_sync_engine(),
            class_=Session,
            expire_on_commit=False,
        )
    return _sync_session_factory


@contextlib.contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Provide a sync database session with auto-commit/rollback.

    Can be used as a context manager (``with get_sync_session() as db:``)
    or as a generator (``gen = get_sync_session(); db = next(gen)``).
    """
    session = get_sync_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def set_rls_context(session: Session, tenant_id: str) -> None:
    """Set RLS tenant context for the current session/transaction.

    HOTFIX (izolacja tenantów): jawnie zapisany scope w ``session.info``
    zasilają filtry ``tenant_id`` w serwisach (RLS nieskuteczne przy roli
    z BYPASSRLS/SUPERUSER). NIL UUID (admin/system) = bez filtra.
    """
    session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
    session.info["tenant_scope"] = None if str(tenant_id) == str(NIL_UUID) else str(tenant_id)
