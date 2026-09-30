import asyncio
import contextlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import *  # noqa: F403 — register all models for autogenerate
from app.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Advisory lock serializujący migracje między kontenerami: backend i
# celery-worker dziedziczą ten sam entrypoint (alembic upgrade head) i przy
# wspólnym starcie wygrywają wyścig o CREATE TYPE/CREATE TABLE — przegrywający
# dostaje unique_violation z pg_type (23505, nie 42710 duplicate_object) i
# kontener pada (deploy 2026-09-02, migracja 044). Lock sesyjny: zwalnia się
# sam przy rozłączeniu (crash kontenera nie blokuje kolejnych prób).
_MIGRATION_ADVISORY_LOCK_ID = 724441


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Lock na OSOBNEJ connection: pg_advisory_lock wykonany na connection
    # migracyjnej otwiera implicit transaction, przez co alembic nie commituje
    # swoich migracji i `async with` przy wyjściu je cofa (zweryfikowane —
    # downgrade "przechodził", a baza zostawała bez zmian). Lock sesyjny jest
    # niezależny od transakcji, więc trzymanie go na drugiej connection
    # serializuje migrantów bez ingerencji w transakcje alembica.
    async with (
        connectable.connect() as lock_connection,
        connectable.connect() as connection,
    ):
        await lock_connection.execute(text(f"SELECT pg_advisory_lock({_MIGRATION_ADVISORY_LOCK_ID})"))
        try:
            await connection.run_sync(do_run_migrations)
        finally:
            # unlock po failed transaction może się nie udać — lock sesyjny
            # zwolni się sam przy zamknięciu lock_connection.
            with contextlib.suppress(Exception):
                await lock_connection.execute(text(f"SELECT pg_advisory_unlock({_MIGRATION_ADVISORY_LOCK_ID})"))

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
