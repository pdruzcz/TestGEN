"""Zadania synchronizacji dwukierunkowej z TMS — Epic 8, Story 8.11 (AC2, AC3, AC6).

Beat co pięć minut przegląda aktywne synchronizacje i wysyła po jednym
zadaniu na każdą zaległą. Sam przebieg idzie osobnym zadaniem, bo rozmowa
z TestRailem czy Jirą przy setce przypadków trwa minuty — gdyby liczył je
skaner, jedna wolna instancja wstrzymywałaby wszystkie pozostałe.

Kolejka ``sync`` jest oddzielona od ``export``: eksport uruchamia użytkownik
i czeka na wynik, synchronizacja chodzi w tle. Wspólna kolejka sprawiłaby,
że kwadransowy cykl synchronizacji opóźniałby ręczny eksport.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_NIL_TENANT = "00000000-0000-0000-0000-000000000000"
_PROVIDER_LABELS = {
    "testrail": "TestRail",
    "xray": "Jira Xray",
    "zephyr": "Zephyr Scale",
}


async def _scan_impl() -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.export.sync_service import due_sync_states

    async with task_session() as session:
        # Skaner patrzy przez wszystkie firmy — stąd bypass RLS identyfikatorem
        # NIL, tak jak zamiatacz webhooków ze Story 8.7.
        await session.execute(text(f"SET LOCAL app.current_tenant = '{_NIL_TENANT}'"))
        due = await due_sync_states(session)
        jobs = [(str(state.id), str(state.tenant_id)) for state in due]

    for sync_state_id, tenant_id in jobs:
        run_sync.delay(sync_state_id, tenant_id)

    logger.info("Skaner synchronizacji: zakolejkowano %d przebiegów", len(jobs))
    return {"dispatched": len(jobs)}


async def _notify_owner(tenant_id: uuid.UUID, provider: str, project_name: str, error: str) -> None:
    """Mail do Ownera o zdegradowanej synchronizacji (AC6) — best effort."""
    from sqlalchemy import select

    from app.core.database import task_session
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.user_tenant import TenantRole, UserTenant
    from app.workers.tasks.email_tasks import send_sync_degraded_email_task

    try:
        async with task_session() as session:
            from sqlalchemy import text

            await session.execute(text(f"SET LOCAL app.current_tenant = '{_NIL_TENANT}'"))
            owner = (
                await session.execute(
                    select(User)
                    .join(UserTenant, UserTenant.user_id == User.id)
                    .where(
                        UserTenant.tenant_id == tenant_id,
                        UserTenant.role == TenantRole.OWNER,
                    )
                    .order_by(UserTenant.created_at)
                    .limit(1)
                )
            ).scalar_one_or_none()
            # Tenant odczytujemy tylko po to, by mail nazwał firmę po imieniu.
            tenant = (
                await session.execute(select(Tenant).where(Tenant.id == tenant_id))
            ).scalar_one_or_none()

        if owner is None:
            logger.warning("Firma %s nie ma Ownera — pomijam powiadomienie", tenant_id)
            return
        label = _PROVIDER_LABELS.get(provider, provider)
        send_sync_degraded_email_task.delay(
            owner.email, label, project_name or (tenant.name if tenant else ""), error
        )
    except Exception:
        logger.warning("Nie udało się powiadomić o degradacji synchronizacji", exc_info=True)


async def _run_impl(sync_state_id: str, tenant_id: str) -> dict:
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.core.encryption import decrypt
    from app.models.integration import IntegrationConfig
    from app.models.project import Project
    from app.models.sync_state import SyncState
    from app.services.export.sync_service import (
        fetch_remote_index,
        record_failure,
        record_success,
        run_pull_sync,
        run_push_sync,
    )
    from app.services.export.tms_exporter import build_exporter, build_tms_client

    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        state = (
            await session.execute(
                select(SyncState).where(
                    SyncState.id == uuid.UUID(sync_state_id),
                    SyncState.tenant_id == tid,
                )
            )
        ).scalar_one_or_none()
        if state is None:
            return {"status": "missing_state"}

        integration = (
            await session.execute(
                select(IntegrationConfig).where(IntegrationConfig.id == state.integration_id)
            )
        ).scalar_one_or_none()
        if integration is None:
            record_failure(state, "Integracja została usunięta", datetime.now(UTC))
            await session.commit()
            return {"status": "missing_integration"}

        settings = dict(integration.settings or {})
        email, _, secret = decrypt(integration.encrypted_credentials).partition(":")
        base_url = integration.base_url
        provider = state.provider
        project = (
            await session.execute(select(Project).where(Project.id == state.project_id))
        ).scalar_one_or_none()
        project_name = project.name if project else ""

        outcome_dict: dict
        degraded = False
        try:
            # Pull przed pushem: zmiany z TMS-a wchodzą do TestGEN, a dopiero
            # potem cały zmieniony stan wraca. Odwrotna kolejność wysyłałaby
            # wersję sprzed rozstrzygnięcia konfliktu i natychmiast ją cofała.
            outcome = None
            if state.pulls:
                client = build_tms_client(provider, base_url, email, secret)
                remote_index = await fetch_remote_index(provider, client, settings)
                outcome = await run_pull_sync(session, state, remote_index)
            if state.pushes:
                exporter = build_exporter(provider, base_url, email, secret, settings)
                pushed = await run_push_sync(session, state, exporter)
                outcome = pushed if outcome is None else outcome.merge(pushed)

            from app.services.export.sync_service import SyncOutcome

            outcome = outcome or SyncOutcome()
            record_success(state, outcome, datetime.now(UTC))
            outcome_dict = outcome.as_dict()
        except Exception as exc:
            logger.error("Synchronizacja %s nie powiodła się: %s", sync_state_id, exc)
            degraded = record_failure(state, str(exc), datetime.now(UTC))
            outcome_dict = {"status": "failed", "error": str(exc)[:500]}

        await session.commit()

    if degraded:
        await _notify_owner(tid, provider, project_name, outcome_dict.get("error", ""))

    return outcome_dict


@celery_app.task(name="sync.scan_due", queue="sync")
def scan_due_syncs() -> dict:
    """Beat co 5 minut: rozsyła przebiegi zaległych synchronizacji (AC2/AC3)."""
    return asyncio.run(_scan_impl())


@celery_app.task(
    bind=True,
    name="sync.run",
    queue="sync",
    max_retries=0,  # ponowienie prowadzi harmonogram; własne dublowałoby przebiegi
)
def run_sync(self, sync_state_id: str, tenant_id: str) -> dict:
    """Jeden przebieg synchronizacji: pull, potem push (AC2/AC3/AC4)."""
    return asyncio.run(_run_impl(sync_state_id, tenant_id))
