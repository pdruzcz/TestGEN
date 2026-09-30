"""Test code generation routes — Epic 3, Story 3.12 (Cypress)."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.codegen import (
    CodeGenRequest,
    CodeGenResponse,
    GeneratedTestCodeOut,
)
from app.services.test_generation.codegen_service import get_generated_code
from app.workers.tasks.analysis_tasks import (
    generate_appium_code,
    generate_cypress_code,
    generate_database_code,
    generate_mstest_code,
    generate_pest_code,
    generate_phpunit_code,
    generate_playwright_code,
    generate_selenium_code,
    generate_sikulix_code,
    generate_testng_code,
    generate_unittest_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["codegen"])


@router.post(
    "/{project_id}/codegen/cypress",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_cypress_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous Cypress code generation from test cases (AC5)."""
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_cypress_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
        payload.base_url,
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/sikulix",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_sikulix_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous SikuliX code generation from test cases (AC6)."""
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_sikulix_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/database",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_database_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous database-layer pytest code generation (Story 1.53, FR70).

    Generuje izolowany kod pytest (``db_session`` + rollback) z wybranych
    przypadków testowych ``test_type = database``. Mirror endpointu Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_database_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/phpunit",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_phpunit_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous PHPUnit (PHP) code generation (Story 1.55, FR24/FR12).

    Generuje klasę testową PHPUnit (``extends TestCase``, ``assertSame``,
    ``expectException``) z wybranych przypadków testowych. Mirror endpointu
    Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_phpunit_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/pest",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_pest_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous Pest (PHP) code generation (Story 1.55, FR24/FR12).

    Generuje testy w DSL Pest (``it()``, ``expect()->toBe()``, ``toThrow``).
    Mirror endpointu Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_pest_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/selenium",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_selenium_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous Selenium code generation (Story 1.56).

    Generuje testy E2E Selenium WebDriver (``.py``, Selenium 4) z wybranych
    przypadków testowych. Mirror endpointu Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_selenium_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/playwright",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_playwright_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous Playwright code generation (Story 1.56).

    Generuje spec-y Playwright (``.spec.ts``, test() + locator API) z wybranych
    przypadków testowych. Mirror endpointu Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_playwright_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/appium",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_appium_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous Appium code generation (Story 1.56).

    Generuje testy mobilne Appium (``.py``, AppiumBy + Page Object Model)
    z wybranych przypadków testowych. ``platform`` (opcjonalnie "android"/"ios")
    wybiera desired capabilities: UiAutomator2 / XCUITest.
    Mirror endpointu Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_appium_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
        payload.platform,
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/unittest",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_unittest_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous unittest (Python) code generation (Story 1.57).

    Generuje klasę ``unittest.TestCase`` (``self.assertEqual…``, uruchamialne
    przez ``python -m unittest``) z wybranych przypadków testowych.
    Mirror endpointu Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_unittest_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/testng",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_testng_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous TestNG (Java 11+) code generation (Story 1.57).

    Generuje klasę z adnotacjami ``@Test``/``@BeforeMethod``
    (``org.testng.annotations``) i asercjami ``Assert.assertEquals``.
    Mirror endpointu Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_testng_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.post(
    "/{project_id}/codegen/mstest",
    status_code=202,
    response_model=CodeGenResponse,
)
async def generate_mstest_route(
    project_id: uuid.UUID,
    payload: CodeGenRequest,
    current_user: User = Depends(get_current_user),
) -> CodeGenResponse:
    """Launch asynchronous MSTest (.NET 8) code generation (Story 1.57).

    Generuje klasę ``[TestClass]`` z ``[TestMethod]`` i asercjami
    ``Assert.AreEqual``. Mirror endpointu Cypress.
    """
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Brak kontekstu organizacji")
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="Nie wskazano żadnego przypadku testowego.")

    result = generate_mstest_code.delay(
        str(project_id),
        str(tenant_id),
        [str(tc) for tc in payload.test_case_ids],
    )
    return CodeGenResponse(task_id=result.id, status="pending")


@router.get(
    "/{project_id}/codegen/{code_id}",
    response_model=GeneratedTestCodeOut,
)
async def get_generated_code_route(
    project_id: uuid.UUID,
    code_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GeneratedTestCodeOut:
    """Fetch a generated test code record with its metadata (AC5)."""
    record = await get_generated_code(db, code_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generated code not found")
    return GeneratedTestCodeOut.model_validate(record)
