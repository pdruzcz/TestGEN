"""Integracje z systemami zarządzania testami — Epic 8, Story 8.8 (TestRail).

Osobny moduł od ``integrations.py`` (prefiks ``/projects``, trackery Jira/ADO)
i od ``integrations_scm.py`` (GitHub/GitLab). Konfiguracja TMS jest jednak
**per projekt**, bo identyfikator projektu docelowego w TestRailu różni się
między projektami TestGEN — stąd ``project_id`` w ścieżce mimo prefiksu
``/integrations``.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_tenant
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import NotFoundError
from app.models.integration import IntegrationConfig, IntegrationProvider
from app.models.project import Project
from app.models.user import User
from app.schemas.export import (
    JiraConfigRequest,
    JiraConfigResponse,
    JiraTestConnectionResponse,
    TestRailConfigRequest,
    TestRailConfigResponse,
    TestRailTestConnectionResponse,
)
from app.services.admin.audit_service import log_action
from app.services.export.jira_tms_service import JiraTmsClient
from app.services.export.jira_tms_service import normalize_url as jira_normalize_url
from app.services.export.testrail_service import TestRailClient, normalize_url
from app.services.export.tms_exporter import (
    DEFAULT_JIRA_PRIORITY_MAP,
    DEFAULT_JIRA_TYPE_LABELS,
    DEFAULT_PRIORITY_MAP,
    DEFAULT_TYPE_MAP,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/testrail", tags=["integrations-tms"])


async def _verify_project(db: AsyncSession, project_id: uuid.UUID, tenant_id: uuid.UUID) -> Project:
    project = (
        await db.execute(
            select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if project is None:
        raise NotFoundError("Projekt nie został znaleziony")
    return project


async def get_testrail_config(
    db: AsyncSession, project_id: uuid.UUID, tenant_id: uuid.UUID
) -> IntegrationConfig:
    """Aktywna konfiguracja TestRaila dla projektu; 404, gdy jej nie ma."""
    config = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.tenant_id == tenant_id,
                IntegrationConfig.provider == IntegrationProvider.TESTRAIL,
                IntegrationConfig.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if config is None:
        raise NotFoundError("Integracja z TestRail nie jest skonfigurowana dla tego projektu")
    return config


def _to_response(config: IntegrationConfig) -> TestRailConfigResponse:
    settings = config.settings or {}
    email = decrypt(config.encrypted_credentials).partition(":")[0]
    return TestRailConfigResponse(
        id=config.id,
        project_id=config.project_id,
        base_url=config.base_url,
        email=email,
        testrail_project_id=settings.get("testrail_project_id"),
        suite_id=settings.get("suite_id"),
        priority_map=settings.get("priority_map") or dict(DEFAULT_PRIORITY_MAP),
        type_map=settings.get("type_map") or dict(DEFAULT_TYPE_MAP),
        field_mapping=settings.get("field_mapping") or {},
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.put(
    "/config",
    response_model=TestRailConfigResponse,
    summary="Zapisz konfigurację integracji z TestRail",
    description=(
        "Zapisuje adres instancji, poświadczenia i mapowania pól dla projektu. "
        "Klucz API jest szyfrowany i nie wraca w odpowiedzi."
    ),
)
async def save_config(
    body: TestRailConfigRequest,
    request: Request,
    project_id: uuid.UUID = Query(..., description="Projekt TestGEN, którego dotyczy konfiguracja"),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> TestRailConfigResponse:
    """Tworzy albo nadpisuje konfigurację TestRaila dla projektu (AC1/AC4)."""
    await _verify_project(db, project_id, tenant_id)

    base_url = normalize_url(body.base_url)
    settings: dict = {
        "testrail_project_id": body.testrail_project_id,
        "suite_id": body.suite_id,
        "priority_map": body.priority_map or dict(DEFAULT_PRIORITY_MAP),
        "type_map": body.type_map or dict(DEFAULT_TYPE_MAP),
        "field_mapping": body.field_mapping or {},
    }
    credentials = encrypt(f"{body.email}:{body.api_key}")

    existing = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.tenant_id == tenant_id,
                IntegrationConfig.provider == IntegrationProvider.TESTRAIL,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.base_url = base_url
        existing.encrypted_credentials = credentials
        existing.settings = settings
        existing.is_active = True
        config = existing
    else:
        config = IntegrationConfig(
            tenant_id=tenant_id,
            project_id=project_id,
            provider=IntegrationProvider.TESTRAIL,
            base_url=base_url,
            encrypted_credentials=credentials,
            settings=settings,
            is_active=True,
        )
        db.add(config)

    await db.flush()
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="integration.testrail.configured",
        resource_type="integration_config",
        resource_id=config.id,
        changes={"base_url": base_url, "testrail_project_id": body.testrail_project_id},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(config)
    return _to_response(config)


@router.get(
    "/config",
    response_model=TestRailConfigResponse,
    summary="Odczytaj konfigurację integracji z TestRail",
)
async def read_config(
    project_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> TestRailConfigResponse:
    """Zapisana konfiguracja projektu — bez klucza API (AC1)."""
    await _verify_project(db, project_id, tenant_id)
    return _to_response(await get_testrail_config(db, project_id, tenant_id))


@router.post(
    "/test",
    response_model=TestRailTestConnectionResponse,
    summary="Sprawdź połączenie z TestRail",
    description=(
        "Wywołuje `get_project` na instancji klienta. Nie tworzy żadnych zasobów — "
        "sprawdza wyłącznie poświadczenia i dostęp do projektu docelowego."
    ),
)
async def test_connection(
    project_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> TestRailTestConnectionResponse:
    """Test poświadczeń i dostępu do projektu w TestRailu (AC1)."""
    await _verify_project(db, project_id, tenant_id)
    config = await get_testrail_config(db, project_id, tenant_id)

    settings = config.settings or {}
    testrail_project_id = settings.get("testrail_project_id")
    if not testrail_project_id:
        return TestRailTestConnectionResponse(
            connected=False, message="Konfiguracja nie zawiera identyfikatora projektu TestRail"
        )

    email, _, api_key = decrypt(config.encrypted_credentials).partition(":")
    client = TestRailClient(config.base_url, email, api_key)
    try:
        result = await client.test_connection(int(testrail_project_id))
    except Exception as exc:
        return TestRailTestConnectionResponse(connected=False, message=str(exc)[:500])

    return TestRailTestConnectionResponse(
        connected=True,
        message=f"Połączono z projektem „{result['project_name']}”",
        project_name=result["project_name"],
    )


# ── Story 8.9: Jira Xray i Zephyr Scale ─────────────────────────────────────

jira_router = APIRouter(prefix="/integrations/jira", tags=["integrations-tms"])

# Wtyczka przekłada się na dostawcę w bazie. Trzymanie ich jako osobnych
# wartości enuma (zamiast jednego „jira" z polem plugin) ma dwa powody:
# provider ``jira`` jest już zajęty przez Story 5.8 (zgłoszenia z luk
# funkcjonalnych, inny kształt ``settings``), a rozdzielenie pozwala projektowi
# korzystać jednocześnie z synchronizacji luk i z eksportu testów.
_PLUGIN_TO_PROVIDER = {
    "xray": IntegrationProvider.XRAY,
    "zephyr": IntegrationProvider.ZEPHYR,
}


async def get_jira_tms_config(
    db: AsyncSession, project_id: uuid.UUID, tenant_id: uuid.UUID
) -> IntegrationConfig:
    """Aktywna konfiguracja Jiry (Xray albo Zephyr) dla projektu."""
    config = (
        await db.execute(
            select(IntegrationConfig)
            .where(
                IntegrationConfig.project_id == project_id,
                IntegrationConfig.tenant_id == tenant_id,
                IntegrationConfig.provider.in_(list(_PLUGIN_TO_PROVIDER.values())),
                IntegrationConfig.is_active.is_(True),
            )
            .order_by(IntegrationConfig.created_at.desc())
        )
    ).scalars().first()
    if config is None:
        raise NotFoundError("Integracja z Jira nie jest skonfigurowana dla tego projektu")
    return config


def _to_jira_response(config: IntegrationConfig) -> JiraConfigResponse:
    settings = config.settings or {}
    email = decrypt(config.encrypted_credentials).partition(":")[0]
    return JiraConfigResponse(
        id=config.id,
        project_id=config.project_id,
        base_url=config.base_url,
        email=email,
        project_key=settings.get("jira_project_key") or "",
        plugin=config.provider.value,
        linked_issue=settings.get("linked_issue"),
        priority_map=settings.get("jira_priority_map") or dict(DEFAULT_JIRA_PRIORITY_MAP),
        type_labels=settings.get("jira_type_labels") or dict(DEFAULT_JIRA_TYPE_LABELS),
        is_active=config.is_active,
        created_at=config.created_at,
    )


@jira_router.put(
    "/config",
    response_model=JiraConfigResponse,
    summary="Zapisz konfigurację integracji z Jira (Xray/Zephyr)",
    description=(
        "Zapisuje adres instancji, poświadczenia, klucz projektu i wybraną wtyczkę. "
        "Token API jest szyfrowany i nie wraca w odpowiedzi.\n\n"
        "Projekt korzysta z jednej wtyczki naraz — wybranie drugiej dezaktywuje poprzednią."
    ),
)
async def save_jira_config(
    body: JiraConfigRequest,
    request: Request,
    project_id: uuid.UUID = Query(..., description="Projekt TestGEN, którego dotyczy konfiguracja"),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> JiraConfigResponse:
    """Tworzy albo nadpisuje konfigurację Jiry dla projektu (AC1/AC5)."""
    await _verify_project(db, project_id, tenant_id)

    provider = _PLUGIN_TO_PROVIDER[body.plugin]
    base_url = jira_normalize_url(body.base_url)
    settings: dict = {
        "jira_project_key": body.project_key.strip().upper(),
        "linked_issue": (body.linked_issue or "").strip() or None,
        "jira_priority_map": body.priority_map or dict(DEFAULT_JIRA_PRIORITY_MAP),
        "jira_type_labels": body.type_labels or dict(DEFAULT_JIRA_TYPE_LABELS),
    }
    credentials = encrypt(f"{body.email}:{body.api_token}")

    rows = list(
        (
            await db.execute(
                select(IntegrationConfig).where(
                    IntegrationConfig.project_id == project_id,
                    IntegrationConfig.tenant_id == tenant_id,
                    IntegrationConfig.provider.in_(list(_PLUGIN_TO_PROVIDER.values())),
                )
            )
        )
        .scalars()
        .all()
    )

    config = next((r for r in rows if r.provider == provider), None)
    if config is not None:
        config.base_url = base_url
        config.encrypted_credentials = credentials
        config.settings = settings
        config.is_active = True
    else:
        config = IntegrationConfig(
            tenant_id=tenant_id,
            project_id=project_id,
            provider=provider,
            base_url=base_url,
            encrypted_credentials=credentials,
            settings=settings,
            is_active=True,
        )
        db.add(config)

    # Jedna wtyczka naraz — inaczej eksport nie wiedziałby, której użyć.
    for other in rows:
        if other.provider != provider:
            other.is_active = False

    await db.flush()
    await log_action(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="integration.jira_tms.configured",
        resource_type="integration_config",
        resource_id=config.id,
        changes={"base_url": base_url, "plugin": body.plugin, "project_key": settings["jira_project_key"]},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(config)
    return _to_jira_response(config)


@jira_router.get(
    "/config",
    response_model=JiraConfigResponse,
    summary="Odczytaj konfigurację integracji z Jira",
)
async def read_jira_config(
    project_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> JiraConfigResponse:
    """Zapisana konfiguracja projektu — bez tokenu (AC1)."""
    await _verify_project(db, project_id, tenant_id)
    return _to_jira_response(await get_jira_tms_config(db, project_id, tenant_id))


@jira_router.post(
    "/test",
    response_model=JiraTestConnectionResponse,
    summary="Sprawdź połączenie z Jira",
    description=(
        "Wywołuje `/myself` i pobiera projekt. Nie tworzy żadnych zasobów — "
        "sprawdza wyłącznie poświadczenia i dostęp do projektu docelowego."
    ),
)
async def test_jira_connection(
    project_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> JiraTestConnectionResponse:
    """Test poświadczeń i dostępu do projektu w Jirze (AC1)."""
    await _verify_project(db, project_id, tenant_id)
    config = await get_jira_tms_config(db, project_id, tenant_id)

    settings = config.settings or {}
    project_key = settings.get("jira_project_key")
    if not project_key:
        return JiraTestConnectionResponse(
            connected=False, message="Konfiguracja nie zawiera klucza projektu Jira"
        )

    email, _, token = decrypt(config.encrypted_credentials).partition(":")
    client = JiraTmsClient(config.base_url, email, token)
    try:
        result = await client.test_connection(str(project_key))
    except Exception as exc:
        return JiraTestConnectionResponse(connected=False, message=str(exc)[:500])

    return JiraTestConnectionResponse(
        connected=True,
        message=f"Połączono z projektem „{result['project_name']}” jako {result['account']}",
        project_name=result["project_name"],
        account=result["account"],
    )
