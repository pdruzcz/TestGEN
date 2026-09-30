from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database import (
    get_engine,
    get_session_factory,
    get_sync_engine,
    get_sync_session_factory,
    task_session,
)


def test_engine_is_configured():
    eng = get_engine()
    assert eng is not None
    assert "asyncpg" in str(eng.url.drivername) or "postgresql" in str(eng.url)


def test_session_factory_creates_async_session():
    session = get_session_factory()()
    assert isinstance(session, AsyncSession)
    assert session.bind is not None


def test_sync_engine_is_configured():
    eng = get_sync_engine()
    assert eng is not None
    assert "postgresql" in str(eng.url)
    assert "asyncpg" not in str(eng.url)


def test_sync_session_factory_creates_sync_session():
    session = get_sync_session_factory()()
    assert isinstance(session, Session)
    assert session.bind is not None


@patch("app.core.database.async_sessionmaker")
@patch("app.core.database.create_async_engine")
async def test_task_session_creates_and_disposes_fresh_engine_per_call(mock_create_engine, mock_sessionmaker):
    """task_session() must build a private engine per call and dispose it on exit.

    This is the loop-safety contract for Celery tasks: they run via
    ``asyncio.run()`` (a fresh event loop each time), so reusing the module-level
    engine from ``get_session_factory()`` would bind asyncpg connections to the
    first loop and raise "Future ... attached to a different loop" on the next.
    Each ``task_session()`` call therefore needs its own engine, disposed on exit.
    """
    engine = MagicMock()
    engine.dispose = AsyncMock()
    mock_create_engine.return_value = engine

    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_sessionmaker.return_value = factory

    async with task_session() as s:
        assert s is session
    mock_create_engine.assert_called_once()
    engine.dispose.assert_awaited_once()

    # Second call builds another fresh engine — no shared singleton.
    engine2 = MagicMock()
    engine2.dispose = AsyncMock()
    mock_create_engine.return_value = engine2
    async with task_session() as s2:
        assert s2 is session
    assert mock_create_engine.call_count == 2
    engine2.dispose.assert_awaited_once()
