"""Zliczanie znalezisk projektu — wspólne dla status checków i bramki CI/CD.

Story 8.3 liczy je, żeby ustawić status na PR; Story 8.4 — żeby zdecydować
o przerwaniu builda. Gdyby każda robiła to po swojemu, te same zmiany
dostawałyby różne werdykty na PR i w pipelinie, a użytkownik nie miałby jak
rozstrzygnąć, który jest prawdziwy.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code_error import CodeError
from app.models.security_finding import FindingStatus, SecurityFinding
from app.services.integrations.status_check_builder import AnalysisOutcome, outcome_from_rows


async def collect_project_outcome(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    pipeline_status: str = "completed",
) -> AnalysisOutcome:
    """Otwarte znaleziska projektu sprowadzone do wspólnej skali wag.

    Bierzemy wyłącznie otwarte — zamknięte i oznaczone jako fałszywe alarmy
    nie mogą blokować kolejnych merge'y ani buildów.
    """
    security_rows = list(
        (
            await session.execute(
                select(SecurityFinding).where(
                    SecurityFinding.project_id == project_id,
                    SecurityFinding.tenant_id == tenant_id,
                    SecurityFinding.status == FindingStatus.OPEN,
                )
            )
        )
        .scalars()
        .all()
    )
    code_error_rows = list(
        (
            await session.execute(
                select(CodeError).where(
                    CodeError.project_id == project_id,
                    CodeError.tenant_id == tenant_id,
                    CodeError.status == "open",
                )
            )
        )
        .scalars()
        .all()
    )
    return outcome_from_rows(security_rows, code_error_rows, pipeline_status)
