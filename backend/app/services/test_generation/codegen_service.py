"""Service layer for Cypress test code generation — Epic 3, Story 3.12.

Loads TestCase rows, drives the registered code generator (CodeGenRegistry —
the "CodeGeneratorFactory" of AC6) and persists the result as TestCode rows
(one per test case). Reuses the existing TestCode model instead of a duplicate
GeneratedTestCode table.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_case import TestCase
from app.models.test_code import TestCode
from app.services.test_generation.codegen import CodeGenConfig, CodeGenRegistry

logger = logging.getLogger(__name__)

# Import pakietu codegen (powyzej) wczytuje generatory przez @register_generator.


def _test_case_to_dict(tc: TestCase) -> dict:
    """Zbuduj slownik wejsciowy dla generatora z modelu TestCase."""
    data = tc.to_dict()
    data["feature_name"] = tc.title
    return data


async def generate_code_for_test_cases(
    db: AsyncSession,
    project_id: uuid.UUID,
    test_case_ids: list[uuid.UUID],
    framework: str = "cypress",
    base_url: str | None = None,
    tenant_id: uuid.UUID | None = None,
    platform: str | None = None,
) -> list[TestCode]:
    """Generuj i utrwal kod testowy dla wybranych test case'ow.

    Dla kazdego test case generowany jest osobny plik (one-to-one),
    co odpowiada relacji TestCode.test_case_id.

    Story 1.56: ``platform`` ("android"/"ios") trafia do ``project_context``
    — Appium buduje z niego desired capabilities (UiAutomator2/XCUITest).
    """
    registry = CodeGenRegistry.get_instance()
    if not registry.is_supported(framework):
        raise ValueError(f"Nieobslugiwany framework: {framework}")

    rows = (await db.execute(select(TestCase).where(TestCase.id.in_(test_case_ids)))).scalars().all()
    if not rows:
        return []

    project_context: dict[str, Any] = {}
    if base_url:
        project_context["base_url"] = base_url
    if platform:
        project_context["platform"] = platform
    config = CodeGenConfig(
        framework=framework,
        validate_compilation=True,
        project_context=project_context or None,
    )
    generator = registry.get_generator(framework, config)

    generated: list[TestCode] = []
    for tc in rows:
        test_file = generator.generate_test_file([_test_case_to_dict(tc)], config)
        record = TestCode(
            test_case_id=tc.id,
            framework=test_file.framework,
            language=test_file.language,
            code=test_file.content,
            file_path=test_file.file_path,
        )
        if tenant_id is not None:
            record.tenant_id = tenant_id
        db.add(record)
        generated.append(record)

    await db.flush()
    return generated


async def get_generated_code(
    db: AsyncSession,
    code_id: uuid.UUID,
) -> TestCode | None:
    """Pobierz pojedynczy rekord wygenerowanego kodu (RLS — tenant scope)."""
    return (await db.execute(select(TestCode).where(TestCode.id == code_id))).scalar_one_or_none()
