import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import get_engine
from app.core.exceptions import TestGENError
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.core.openapi_enrichment import setup_openapi
from app.core.redis import close_redis_pool
from app.core.storage import ensure_bucket_exists

logger = logging.getLogger(__name__)


async def _warn_rls_ineffective() -> None:
    """HOTFIX (izolacja tenantów, 2026-09-15): rola z BYPASSRLS/SUPERUSER
    omija polityki RLS — zamiast wymagać bypassu (stary check, który
    dezaktywował RLS), ostrzegamy głośno. Izolacja pilnuje jawny filtr
    ``tenant_id`` w serwisach (db.info["tenant_scope"]); docelowe pełne
    RLS = dedykowana rola bez bypassu + FORCE ROW LEVEL SECURITY (follow-up).
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(get_engine()) as session:
        result = await session.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"))
        row = result.one_or_none()
        if row is None:
            logger.warning("Nie można odczytać atrybutów roli DB (pg_roles) — pomijam kontrolę")
            return
        if row.rolsuper or row.rolbypassrls:
            logger.warning(
                "RLS NIESKUTECZNE: rola DB %s SUPERUSER/BYPASSRLS — polityki RLS są omijane. "
                "Izolacja tenantów opiera się na jawnych filtrach tenant_id w serwisach. "
                "Docelowo: ALTER ROLE <role> NOSUPERUSER NOBYPASSRLS + FORCE ROW LEVEL SECURITY.",
                "jest" if row.rolsuper else "ma",
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _ = app
    setup_logging()
    settings = get_settings()
    # ENCRYPTION_KEY validation is now in Settings._validate_production_settings()
    logger.info("TestGEN starting up")
    await _warn_rls_ineffective()
    # Admin bootstrap — create platform admin from env vars if enabled and none exists.
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.services.auth.bootstrap import bootstrap_admin

        async with AsyncSession(get_engine()) as session:
            await bootstrap_admin(session, settings)
    except Exception as exc:
        logger.warning("Admin bootstrap skipped: %s", exc)
    # Subscription plans seed — idempotent upsert, ceny z env (Story 7.1/AC5):
    # wymiana cen = zmiana env + restart, bez deployu kodu.
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.seed.seed_plans import seed_subscription_plans

        async with AsyncSession(get_engine()) as session:
            await seed_subscription_plans(session)
            await session.commit()
    except Exception as exc:
        logger.warning("Subscription plans seed skipped: %s", exc)
    # MinIO bucket bootstrap — non-fatal (tests / early dev may not have MinIO up).
    try:
        await asyncio.to_thread(ensure_bucket_exists, settings.minio_bucket_name)
    except Exception as exc:
        logger.warning("MinIO bucket init skipped: %s", exc)
    yield
    logger.info("TestGEN shutting down")
    await close_redis_pool()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "TestGEN — platforma do automatycznego generowania przypadków testowych. Dokumentacja: docs/final/"
        ),
        version="0.1.0",
        openapi_tags=[
            {
                "name": "documents",
                "description": "Analiza dokumentacji: status, sekcje, klasyfikacja, wymagania, glosariusz, niespójności",
            },
            {"name": "projects", "description": "Projekty i upload plików (dokumentacja, kod, UML, GUI)"},
            {"name": "test-cases", "description": "Zarządzanie przypadkami testowymi (CRUD, wykonanie, przegląd)"},
            {"name": "traceability", "description": "Macierz śledzenia źródeł UML/GUI (Epic 3)"},
            {"name": "health", "description": "Sonde zdrowia usługi"},
        ],
        openapi_url="/openapi.json" if settings.debug else None,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        swagger_ui_parameters={
            # Klucz wpisany w „Authorize" przeżywa odświeżenie strony —
            # bez tego każda próba wywołania zaczyna się od wklejania go na nowo.
            "persistAuthorization": True,
            "docExpansion": "none",
            "filter": True,
            "tryItOutEnabled": True,
        },
        lifespan=lifespan,
    )

    # Story 8.5: bezpieczeństwo, limity i przykłady wywołań w schemie OpenAPI.
    # Adres serwera bierzemy z konfiguracji, żeby przykłady dało się wkleić
    # i uruchomić bez podmieniania hosta.
    setup_openapi(app, settings.api_public_base_url)

    setup_middleware(app)

    @app.exception_handler(TestGENError)
    async def testgen_error_handler(request: Request, exc: TestGENError) -> JSONResponse:
        headers = {}
        if retry_after := exc.extra.get("retry_after"):
            headers["Retry-After"] = str(retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_rfc7807(instance=str(request.url.path)),
            media_type="application/problem+json",
            headers=headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Sanitize errors for JSON serialization (strip non-serializable ctx objects)
        errors = []
        for err in exc.errors():
            clean = {k: v for k, v in err.items() if k != "ctx"}
            errors.append(clean)
        return JSONResponse(
            status_code=422,
            content={
                "type": "https://testgen.io/errors/validation-error",
                "title": "Validation Error",
                "status": 422,
                "detail": "Request validation failed",
                "instance": str(request.url.path),
                "errors": errors,
            },
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "type": "https://testgen.io/errors/internal-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred",
                "instance": str(request.url.path),
            },
            media_type="application/problem+json",
        )

    app.include_router(api_router)

    # Story 7.3 (AC6): metryki Prometheus (webhook_processed_total,
    # webhook_processing_seconds) — scrape przez /metrics.
    from prometheus_client import make_asgi_app

    app.mount("/metrics", make_asgi_app())

    return app


app = create_app()
