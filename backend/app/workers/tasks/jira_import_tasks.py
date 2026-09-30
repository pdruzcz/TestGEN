"""Import wymagań z Jiry — Epic 8, Story 8.12 (AC1, AC2, AC3, AC4).

Import idzie w tle, bo składa się z wielu żądań do Jiry: zapytanie JQL ze
stronicowaniem plus jedno pobranie na każdy załącznik. Przy kilkudziesięciu
historyjkach z diagramami to minuty pracy — żądanie HTTP padłoby na timeoucie
proxy.

Postęp raportujemy przez ``TaskProgressService``, tym samym mechanizmem, co
analizy i eksporty, więc ekran importu nie potrzebuje własnego.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Górna granica pobieranych załączników w jednym przebiegu. Projekt Jiry
# potrafi mieć ich tysiące, a import ma wnieść dokumentację, nie zrobić
# kopii zapasowej cudzego systemu.
MAX_ATTACHMENTS = 200
# Pojedynczy załącznik większy niż to pomijamy — nagranie ekranu ani zrzut
# bazy nie są dokumentacją, a zjadłyby limit miejsca projektu.
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


async def _import_impl(task_id: str, import_id: str, tenant_id: str) -> dict:
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.core.encryption import decrypt
    from app.models.integration import IntegrationConfig
    from app.models.jira_import import JiraImport, JiraImportStatus
    from app.models.project import Project
    from app.services.integrations import jira_import_service as svc
    from app.services.integrations.jira_service import JiraImportClient
    from app.services.project.upload_service import _persist_file_bytes
    from app.services.task_progress_service import TaskProgressService

    progress = TaskProgressService()
    tid = uuid.UUID(tenant_id)
    started_at = datetime.now(UTC)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        record = (
            await session.execute(
                select(JiraImport).where(
                    JiraImport.id == uuid.UUID(import_id),
                    JiraImport.tenant_id == tid,
                )
            )
        ).scalar_one_or_none()
        if record is None:
            progress.fail_task(task_id, "Import nie istnieje")
            return {"status": "missing_import"}

        integration = (
            await session.execute(select(IntegrationConfig).where(IntegrationConfig.id == record.integration_id))
        ).scalar_one_or_none()
        if integration is None:
            record.status = JiraImportStatus.FAILED
            record.last_error = "Integracja z Jirą została usunięta"
            await session.commit()
            progress.fail_task(task_id, record.last_error)
            return {"status": "missing_integration"}

        project = (await session.execute(select(Project).where(Project.id == record.project_id))).scalar_one_or_none()
        if project is None:
            record.status = JiraImportStatus.FAILED
            record.last_error = "Projekt nie istnieje"
            await session.commit()
            progress.fail_task(task_id, record.last_error)
            return {"status": "missing_project"}

        record.status = JiraImportStatus.RUNNING
        record.task_id = task_id
        await session.commit()

        try:
            # Wewnątrz try od pierwszego ruchu na sieć: decrypt()/klient padały
            # przed handlerem i import wisiał w „running" po śmierci taska.
            email, _, token = decrypt(integration.encrypted_credentials).partition(":")
            client = JiraImportClient(integration.base_url, email, token)
            jql = svc.build_jql(record.jira_project_key, list(record.issue_types or []), record.last_import_at)

            progress.update_progress(task_id, 10, "Pobieram zgłoszenia z Jiry")
            issues = await client.search_issues(jql)

            progress.update_progress(task_id, 35, f"Przetwarzam {len(issues)} zgłoszeń")
            outcome = svc.convert_all(issues)

            document = await _ensure_document(session, record, project, outcome.requirements)
            await _persist_requirements(session, project, document, outcome.requirements)

            progress.update_progress(task_id, 60, "Pobieram załączniki")
            outcome.attachments = await _download_attachments(
                session, project, client, svc.attachments_of(issues), _persist_file_bytes
            )

            record.status = JiraImportStatus.COMPLETED
            # Znacznik przesuwamy dopiero tutaj: gdyby szedł przed pobraniem,
            # przerwany import zabrałby ze sobą zgłoszenia, których nie zdążył
            # przetworzyć — następny przebieg już by o nie nie zapytał.
            record.last_import_at = started_at
            record.total_imported = len(outcome.requirements)
            record.total_attachments = outcome.attachments
            record.total_skipped = outcome.skipped
            record.last_error = "; ".join(outcome.errors)[:2000] or None
            await session.commit()

            document_id = str(document.id)
            project_id = str(record.project_id)
            summary = outcome.as_dict()
        except Exception as exc:
            logger.error("Import z Jiry %s nie powiódł się: %s", import_id, exc)
            record.status = JiraImportStatus.FAILED
            record.last_error = str(exc)[:2000]
            await session.commit()
            progress.fail_task(task_id, str(exc)[:500])
            return {"status": "failed", "error": str(exc)[:500]}

    progress.update_progress(task_id, 90, "Uruchamiam analizę luk")
    _trigger_gap_analysis(project_id, document_id, tenant_id)

    progress.complete_task(task_id, f"/api/v1/projects/{project_id}/import/jira/status")
    logger.info(
        "Import z Jiry zakończony: wymagań=%d załączników=%d pominiętych=%d",
        summary["imported"],
        summary["attachments"],
        summary["skipped"],
    )
    return {"status": "completed", **summary}


async def _ensure_document(session, record, project, requirements: list[dict]):
    """Zakłada albo odświeża syntetyczny dokument z zaimportowanymi wymaganiami.

    Przy imporcie przyrostowym dokument już istnieje — nadpisujemy jego treść
    zamiast zakładać drugi, inaczej wymagania rozjechałyby się na kilka
    „dokumentów" różniących się wyłącznie datą.
    """
    from sqlalchemy import select

    from app.models.source_file import (
        DocumentFormat,
        FileCategory,
        FileProcessingStatus,
        SourceFile,
    )
    from app.services.integrations import jira_import_service as svc

    content = svc.render_document(record.jira_project_key, requirements).encode("utf-8")
    filename = f"jira-{record.jira_project_key}.md"

    document = None
    if record.document_file_id is not None:
        document = (
            await session.execute(select(SourceFile).where(SourceFile.id == record.document_file_id))
        ).scalar_one_or_none()

    if document is None:
        document = SourceFile(
            tenant_id=project.tenant_id,
            project_id=project.id,
            filename=filename,
            original_path=f"jira://{record.jira_project_key}",
            storage_key=f"{project.tenant_id}/{project.id}/jira-{record.jira_project_key}.md",
            file_size=len(content),
            mime_type="text/markdown",
            sha256_hash=_sha256(content),
            file_category=FileCategory.DOCUMENTATION,
            doc_format=DocumentFormat.MARKDOWN,
            processing_status=FileProcessingStatus.READY,
        )
        session.add(document)
        await session.flush()
        record.document_file_id = document.id
    else:
        document.file_size = len(content)
        document.sha256_hash = _sha256(content)
        document.processing_status = FileProcessingStatus.READY

    await _upload_document(document.storage_key, content)
    return document


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


async def _upload_document(storage_key: str, content: bytes) -> None:
    """Zapis treści dokumentu do magazynu — nieudany nie przerywa importu.

    Wymagania są już w bazie; brak pliku oznacza tylko, że nie da się go
    pobrać, a nie że import się nie odbył.
    """
    import io

    from app.core.config import get_settings
    from app.core.storage import upload_file

    try:
        await asyncio.to_thread(
            upload_file,
            get_settings().minio_bucket_name,
            storage_key,
            io.BytesIO(content),
            len(content),
            "text/markdown",
        )
    except Exception:
        logger.warning("Nie udało się zapisać dokumentu %s", storage_key, exc_info=True)


async def _persist_requirements(session, project, document, requirements: list[dict]) -> None:
    """Zapisuje wymagania i udawane przetworzenie dokumentu (AC2)."""
    from sqlalchemy import select

    from app.models.analysis_result import AnalysisResult, AnalysisStatus, EngineMode
    from app.services.analysis.document.requirement_extractor import from_result_data
    from app.services.integrations import jira_import_service as svc

    existing_req = (
        await session.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document.id,
                AnalysisResult.module == "requirements",
            )
        )
    ).scalar_one_or_none()

    previous = from_result_data(existing_req.result_data) if existing_req else []
    merged = svc.merge_requirements(previous, requirements)

    if existing_req is None:
        session.add(
            AnalysisResult(
                tenant_id=project.tenant_id,
                project_id=project.id,
                source_file_id=document.id,
                engine_mode=EngineMode.NATIVE,
                module="requirements",
                status=AnalysisStatus.COMPLETED,
                result_data=svc.requirements_payload(merged),
            )
        )
    else:
        existing_req.result_data = svc.requirements_payload(merged)
        existing_req.status = AnalysisStatus.COMPLETED

    existing_prep = (
        await session.execute(
            select(AnalysisResult).where(
                AnalysisResult.source_file_id == document.id,
                AnalysisResult.module == "document_preprocessing",
            )
        )
    ).scalar_one_or_none()

    payload = svc.sections_payload(merged)
    payload["document_structure"]["filename"] = document.filename
    if existing_prep is None:
        session.add(
            AnalysisResult(
                tenant_id=project.tenant_id,
                project_id=project.id,
                source_file_id=document.id,
                engine_mode=EngineMode.NATIVE,
                module="document_preprocessing",
                status=AnalysisStatus.COMPLETED,
                result_data=payload,
            )
        )
    else:
        existing_prep.result_data = payload
        existing_prep.status = AnalysisStatus.COMPLETED


async def _download_attachments(session, project, client, attachments, persist) -> int:
    """Pobiera załączniki i zapisuje je jako pliki projektu (AC3).

    Duplikaty odpadają na sicie SHA-256 w ``_persist_file_bytes`` — ten sam
    diagram dołączony do trzech historyjek zapisuje się raz (AC4).
    """
    saved = 0
    saved_files: list = []
    for issue_key, attachment in attachments[:MAX_ATTACHMENTS]:
        size = int(attachment.get("size") or 0)
        if size > MAX_ATTACHMENT_BYTES:
            logger.info(
                "Pomijam załącznik %s z %s — %d B przekracza limit",
                attachment.get("filename"),
                issue_key,
                size,
            )
            continue
        try:
            data = await client.get_attachment_content(str(attachment["id"]))
        except Exception as exc:
            # Jeden niedostępny załącznik nie może unieważnić całego importu.
            logger.warning("Nie pobrano załącznika %s: %s", attachment.get("filename"), exc)
            continue

        source_file = await persist(
            session,
            project,
            filename=str(attachment["filename"]),
            original_path=f"jira://{issue_key}/{attachment['filename']}",
            data=data,
            mime_type=attachment.get("mime_type"),
        )
        if source_file is not None:
            saved += 1
            saved_files.append(source_file)
    await session.commit()
    # Preprocessing dispatchujemy dopiero po commicie — worker czyta wiersz
    # SourceFile z bazy, a przed commitem byłby niewidoczny (wyścig).
    for source_file in saved_files:
        _trigger_preprocessing(source_file, project)
    return saved


def _trigger_gap_analysis(project_id: str, document_id: str, tenant_id: str) -> None:
    """Analiza luk na zaimportowanych wymaganiach (AC2) — best effort."""
    try:
        from app.workers.tasks.gap_tasks import run_gap_analysis

        run_gap_analysis.delay(project_id, [document_id], tenant_id)
    except Exception:
        logger.warning("Nie udało się uruchomić analizy luk po imporcie", exc_info=True)


def _trigger_preprocessing(source_file, project) -> None:
    """Preprocessing załączników-dokumentacji po imporcie — best effort.

    Bez tego PDF-y z Jiry zostawały w stanie ``uploaded`` i wieczyście
    „analizowały się" w UI — nikt nie dispatchował ``parse_document_task``
    (mechanizm znany z ręcznego uploadu). Załączniki bez ``doc_format``
    (obrazki itp.) zostają bez parsowania — jak przy uploadie ręcznym.
    """
    if not source_file.doc_format:
        return
    try:
        from app.workers.tasks.document_tasks import parse_document_task

        parse_document_task.delay(str(source_file.id), str(project.tenant_id))
    except Exception:
        logger.warning(
            "Nie udało się uruchomić parsowania załącznika %s",
            source_file.filename,
            exc_info=True,
        )


@celery_app.task(
    bind=True,
    name="jira.import_requirements",
    queue="sync",
    max_retries=0,  # ponowienie pobrałoby te same zgłoszenia jeszcze raz
)
def import_from_jira_task(self, import_id: str, tenant_id: str) -> dict:
    """Jeden przebieg importu z Jiry (AC1-AC4)."""
    return asyncio.run(_import_impl(self.request.id or import_id, import_id, tenant_id))
