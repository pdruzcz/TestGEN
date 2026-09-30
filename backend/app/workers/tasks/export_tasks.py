"""Eksport przypadków testowych do TMS — Epic 8, Story 8.8 (AC2).

Eksport idzie w tle, bo TestRail dławi tempo żądań: setka przypadków to
setka wywołań w odstępach sekundowych, czyli minuty pracy. Żądanie HTTP
z takim czasem odpowiedzi padłoby na timeoucie proxy.

Postęp raportujemy przez ``TaskProgressService`` — ten sam mechanizm, którym
frontend śledzi analizy, więc ekran eksportu nie potrzebuje własnego.
"""

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _build_exporter(provider: str, base_url: str, email: str, secret: str, settings: dict):
    """Eksporter właściwy dla dostawcy — wspólna fabryka ze Story 8.11."""
    from app.services.export.tms_exporter import build_exporter

    return build_exporter(provider, base_url, email, secret, settings)


_PROVIDER_LABELS = {
    "testrail": "TestRail",
    "xray": "Jira Xray",
    "zephyr": "Zephyr Scale",
}


async def _export_impl(
    task_id: str,
    tenant_id: str,
    project_id: str,
    integration_config_id: str,
    test_case_ids: list[str],
    provider: str = "testrail",
) -> dict:
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.core.encryption import decrypt
    from app.models.analysis_result import AnalysisResult
    from app.models.integration import IntegrationConfig
    from app.models.test_case import TestCase
    from app.services.export.tms_exporter import rows_from_test_cases
    from app.services.task_progress_service import TaskProgressService

    progress_svc = TaskProgressService()
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        config_row = (
            await session.execute(
                select(IntegrationConfig).where(
                    IntegrationConfig.id == uuid.UUID(integration_config_id),
                    IntegrationConfig.tenant_id == tid,
                )
            )
        ).scalar_one_or_none()
        if config_row is None:
            label = _PROVIDER_LABELS.get(provider, provider)
            progress_svc.fail_task(task_id, f"Konfiguracja {label} nie istnieje")
            return {"status": "failed", "error": "missing_config"}

        # TestCase nie ma ``project_id`` — wiąże się z projektem przez AnalysisResult.
        stmt = select(TestCase).where(
            TestCase.tenant_id == tid,
            TestCase.analysis_result_id.in_(
                select(AnalysisResult.id).where(
                    AnalysisResult.project_id == uuid.UUID(project_id)
                )
            ),
        )
        if test_case_ids:
            stmt = stmt.where(TestCase.id.in_([uuid.UUID(i) for i in test_case_ids]))
        test_cases = list((await session.execute(stmt)).scalars().all())

        settings = dict(config_row.settings or {})
        # Poświadczenia trzymamy w formacie ``email:klucz`` — tak jak Jira i ADO
        # (Story 5.8), więc jeden mechanizm szyfrowania obsługuje wszystkie TMS-y.
        email, _, api_key = decrypt(config_row.encrypted_credentials).partition(":")
        base_url = config_row.base_url

    if not test_cases:
        progress_svc.complete_task(task_id, f"/api/v1/projects/{project_id}/test-cases")
        return {"status": "completed", "created": 0, "updated": 0, "failed": 0, "total": 0}

    rows = rows_from_test_cases(test_cases)
    label = _PROVIDER_LABELS.get(provider, provider)
    progress_svc.update_progress(task_id, 5, f"Eksport {len(rows)} przypadków do {label}")

    exporter = _build_exporter(provider, base_url, email, api_key, settings)

    def _report(done: int, total: int) -> None:
        # 5-95%: początek zarezerwowany na odczyt sekcji, koniec na podsumowanie.
        percent = 5 + int(90 * done / max(total, 1))
        progress_svc.update_progress(task_id, percent, f"Wyeksportowano {done} z {total}")

    try:
        result = await exporter.export(rows, progress=_report)
    except Exception as exc:
        logger.error("Eksport do %s nie powiódł się: %s", label, exc)
        progress_svc.fail_task(task_id, str(exc)[:500])
        raise

    progress_svc.complete_task(task_id, f"/api/v1/projects/{project_id}/test-cases")
    logger.info(
        "Eksport do %s zakończony: utworzono=%d zaktualizowano=%d nieudane=%d",
        label,
        result.created,
        result.updated,
        result.failed,
    )
    return {"status": "completed", **result.as_dict()}


@celery_app.task(
    bind=True,
    name="export.testrail",
    queue="export",
    max_retries=0,  # ponowienie powtórzyłoby już utworzone przypadki
)
def export_to_testrail(
    self,
    tenant_id: str,
    project_id: str,
    integration_config_id: str,
    test_case_ids: list[str],
) -> dict:
    """Eksportuje wskazane przypadki testowe do TestRaila (Story 8.8)."""
    return asyncio.run(
        _export_impl(
            self.request.id, tenant_id, project_id, integration_config_id, test_case_ids, "testrail"
        )
    )


@celery_app.task(
    bind=True,
    name="export.jira_tms",
    queue="export",
    max_retries=0,  # jak wyżej: ponowienie duplikowałoby utworzone testy
)
def export_to_jira_tms(
    self,
    tenant_id: str,
    project_id: str,
    integration_config_id: str,
    test_case_ids: list[str],
    provider: str,
) -> dict:
    """Eksportuje przypadki do Jiry przez Xray albo Zephyr Scale (Story 8.9)."""
    return asyncio.run(
        _export_impl(
            self.request.id, tenant_id, project_id, integration_config_id, test_case_ids, provider
        )
    )
