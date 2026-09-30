"""Zadanie importu z Jiry — Story 8.12 (Task 6.1, AC3, AC4).

Sesja bazy, klient Jiry i zapis plików są podstawiane; sprawdzamy, co zadanie
robi ze stanem importu i z załącznikami.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.elements import TextClause

from app.models.jira_import import JiraImport, JiraImportStatus
from app.services.integrations.jira_service import JiraIssue

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def bez_postepu():
    """``TaskProgressService`` rozmawia z Redisem — w teście nie ma go z czym."""
    with patch("app.services.task_progress_service.TaskProgressService", MagicMock()):
        yield


def _record(**overrides) -> JiraImport:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "integration_id": uuid.uuid4(),
        "jira_project_key": "QA",
        "issue_types": ["Story"],
        "status": JiraImportStatus.PENDING,
        "last_import_at": None,
        "total_imported": 0,
        "total_attachments": 0,
        "total_skipped": 0,
        "document_file_id": None,
    }
    defaults.update(overrides)
    return JiraImport(**defaults)


def _integration():
    from app.core.encryption import encrypt

    integration = MagicMock()
    integration.base_url = "https://firma.atlassian.net"
    integration.encrypted_credentials = encrypt("qa@firma.pl:token")
    return integration


def _project():
    project = MagicMock()
    project.id = uuid.uuid4()
    project.tenant_id = uuid.uuid4()
    return project


def _session(*rows) -> AsyncMock:
    session = AsyncMock()
    pending = list(rows)

    def _next(statement, *args, **kwargs):
        result = MagicMock()
        if isinstance(statement, TextClause):
            return result
        result.scalar_one_or_none.return_value = pending.pop(0) if pending else None
        return result

    session.execute.side_effect = _next
    session.add = MagicMock()
    return session


@asynccontextmanager
async def _session_cm(session):
    yield session


def _factory(session):
    return lambda: _session_cm(session)


def _issue(**overrides) -> JiraIssue:
    defaults = {
        "key": "QA-1",
        "issue_type": "Story",
        "summary": "Historyjka",
        "description": "h2. Acceptance Criteria\n* Kryterium\n",
        "priority": "High",
        "labels": [],
        "status": "To Do",
        "updated": "2026-09-25T10:00:00.000+0000",
        "epic_key": None,
        "parent_key": None,
        "attachments": [],
    }
    defaults.update(overrides)
    return JiraIssue(**defaults)


def _patches(record, session, issues, attachment_bytes=b"dane"):
    """Wspólny zestaw podstawień dla przebiegu importu."""
    client = MagicMock(
        search_issues=AsyncMock(return_value=issues),
        get_attachment_content=AsyncMock(return_value=attachment_bytes),
    )
    persist = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    return client, persist


@pytest.mark.asyncio
async def test_udany_import_zapisuje_liczniki_i_znacznik():
    from app.workers.tasks import jira_import_tasks as tasks

    record = _record()
    session = _session(record, _integration(), _project())
    client, persist = _patches(record, session, [_issue()])

    with (
        patch("app.core.database.task_session", _factory(session)),
        patch("app.services.integrations.jira_service.JiraImportClient", return_value=client),
        patch("app.services.project.upload_service._persist_file_bytes", persist),
        patch.object(tasks, "_ensure_document", AsyncMock(return_value=MagicMock(id=uuid.uuid4()))),
        patch.object(tasks, "_persist_requirements", AsyncMock()),
        patch.object(tasks, "_trigger_gap_analysis", MagicMock()),
    ):
        summary = await tasks._import_impl("t1", str(record.id), str(record.tenant_id))

    assert summary["status"] == "completed"
    assert summary["imported"] == 1
    assert record.status is JiraImportStatus.COMPLETED
    assert record.last_import_at is not None
    assert record.total_imported == 1


@pytest.mark.asyncio
async def test_nieudany_import_nie_przesuwa_znacznika():
    from app.workers.tasks import jira_import_tasks as tasks

    poprzedni = NOW - timedelta(days=1)
    record = _record(last_import_at=poprzedni)
    session = _session(record, _integration(), _project())
    client = MagicMock(search_issues=AsyncMock(side_effect=RuntimeError("Jira nie odpowiada")))

    with (
        patch("app.core.database.task_session", _factory(session)),
        patch("app.services.integrations.jira_service.JiraImportClient", return_value=client),
    ):
        summary = await tasks._import_impl("t1", str(record.id), str(record.tenant_id))

    assert summary["status"] == "failed"
    assert record.status is JiraImportStatus.FAILED
    # Gdyby znacznik poszedł do przodu, następny import pominąłby zgłoszenia,
    # których ten nie zdążył pobrać.
    assert record.last_import_at == poprzedni


@pytest.mark.asyncio
async def test_nieczytelne_poswiadczenia_koncza_import_bledem():
    """Deszyfrowanie poświadczeń pada między „running" a try (2026-09-28):
    wyjątek uciekał poza handler i import wisiał w „running" na zawsze."""
    from app.workers.tasks import jira_import_tasks as tasks

    record = _record()
    integration = _integration()
    integration.encrypted_credentials = "uszkodzone-dane"  # nie jest tokenem Fernet
    session = _session(record, integration, _project())

    with patch("app.core.database.task_session", _factory(session)):
        summary = await tasks._import_impl("t1", str(record.id), str(record.tenant_id))

    assert summary["status"] == "failed"
    assert record.status is JiraImportStatus.FAILED
    assert record.last_error is not None


@pytest.mark.asyncio
async def test_usunieta_integracja_konczy_import_bledem():
    from app.workers.tasks import jira_import_tasks as tasks

    record = _record()
    session = _session(record, None)

    with patch("app.core.database.task_session", _factory(session)):
        summary = await tasks._import_impl("t1", str(record.id), str(record.tenant_id))

    assert summary["status"] == "missing_integration"
    assert record.last_error == "Integracja z Jirą została usunięta"


@pytest.mark.asyncio
async def test_nieistniejacy_import_konczy_sie_spokojnie():
    from app.workers.tasks import jira_import_tasks as tasks

    session = _session(None)

    with patch("app.core.database.task_session", _factory(session)):
        summary = await tasks._import_impl("t1", str(uuid.uuid4()), str(uuid.uuid4()))

    assert summary["status"] == "missing_import"


# ── załączniki ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zbyt_duzy_zalacznik_jest_pomijany():
    from app.workers.tasks import jira_import_tasks as tasks

    session = AsyncMock()
    client = MagicMock(get_attachment_content=AsyncMock())
    attachments = [("QA-1", {"id": "1", "filename": "nagranie.mp4", "size": tasks.MAX_ATTACHMENT_BYTES + 1})]

    saved = await tasks._download_attachments(session, _project(), client, attachments, AsyncMock())

    assert saved == 0
    client.get_attachment_content.assert_not_called()


@pytest.mark.asyncio
async def test_niedostepny_zalacznik_nie_przerywa_importu():
    from app.workers.tasks import jira_import_tasks as tasks

    session = AsyncMock()
    client = MagicMock(get_attachment_content=AsyncMock(side_effect=[RuntimeError("403"), b"dane"]))
    persist = AsyncMock(return_value=MagicMock())
    attachments = [
        ("QA-1", {"id": "1", "filename": "tajne.pdf", "size": 10}),
        ("QA-2", {"id": "2", "filename": "diagram.png", "size": 10}),
    ]

    with patch.object(tasks, "_trigger_preprocessing"):
        saved = await tasks._download_attachments(session, _project(), client, attachments, persist)

    assert saved == 1


@pytest.mark.asyncio
async def test_duplikat_zalacznika_nie_jest_liczony():
    from app.workers.tasks import jira_import_tasks as tasks

    session = AsyncMock()
    client = MagicMock(get_attachment_content=AsyncMock(return_value=b"dane"))
    # ``_persist_file_bytes`` zwraca None, gdy plik o tym samym SHA-256
    # już jest w projekcie — ten sam diagram w trzech historyjkach zapisze
    # się raz (AC4).
    persist = AsyncMock(side_effect=[MagicMock(), None, None])
    attachments = [("QA-1", {"id": str(i), "filename": "diagram.png", "size": 10}) for i in range(3)]

    with patch.object(tasks, "_trigger_preprocessing"):
        saved = await tasks._download_attachments(session, _project(), client, attachments, persist)

    assert saved == 1


@pytest.mark.asyncio
async def test_liczba_zalacznikow_jest_ograniczona():
    from app.workers.tasks import jira_import_tasks as tasks

    session = AsyncMock()
    client = MagicMock(get_attachment_content=AsyncMock(return_value=b"dane"))
    persist = AsyncMock(return_value=MagicMock())
    attachments = [
        ("QA-1", {"id": str(i), "filename": f"plik-{i}.png", "size": 10}) for i in range(tasks.MAX_ATTACHMENTS + 10)
    ]

    with patch.object(tasks, "_trigger_preprocessing"):
        saved = await tasks._download_attachments(session, _project(), client, attachments, persist)

    assert saved == tasks.MAX_ATTACHMENTS


@pytest.mark.asyncio
async def test_zalacznik_dostaje_preprocessing_po_zapisie():
    """PDF-y z Jiry zostawały w ``uploaded`` na zawsze — nikt nie dispatchował
    parsowania (2026-09-29). Teraz każdy zapisany załącznik je dostaje,
    dopiero PO commicie (worker musi widzieć wiersz w bazie)."""
    from app.workers.tasks import jira_import_tasks as tasks

    session = AsyncMock()
    client = MagicMock(get_attachment_content=AsyncMock(return_value=b"dane"))
    persist = AsyncMock(return_value=MagicMock(doc_format="pdf"))
    attachments = [("QA-1", {"id": "1", "filename": "spec.pdf", "size": 10})]

    order: list[str] = []
    session.commit.side_effect = lambda: order.append("commit")

    with patch.object(
        tasks,
        "_trigger_preprocessing",
        side_effect=lambda *a: order.append("preprocessing"),
    ):
        saved = await tasks._download_attachments(session, _project(), client, attachments, persist)

    assert saved == 1
    assert order == ["commit", "preprocessing"]


@pytest.mark.asyncio
async def test_niedostepny_zalacznik_bez_preprocessingu():
    from app.workers.tasks import jira_import_tasks as tasks

    session = AsyncMock()
    client = MagicMock(get_attachment_content=AsyncMock(return_value=b"dane"))
    # persist zwrócił None (duplikat SHA-256) — nic nie było zapisane,
    # więc nic nie dostaje preprocessingu.
    persist = AsyncMock(return_value=None)
    attachments = [("QA-1", {"id": "1", "filename": "diagram.png", "size": 10})]

    with patch.object(tasks, "_trigger_preprocessing") as trigger:
        await tasks._download_attachments(session, _project(), client, attachments, persist)

    trigger.assert_not_called()


def test_preprocessing_dispatchowany_dla_dokumentacji():
    from app.workers.tasks import jira_import_tasks as tasks

    source_file = MagicMock(doc_format="pdf", id=uuid.uuid4())
    with patch("app.workers.tasks.document_tasks.parse_document_task") as parse:
        tasks._trigger_preprocessing(source_file, _project())

    parse.delay.assert_called_once()


def test_preprocessing_pomijany_dla_niedokumentacji():
    from app.workers.tasks import jira_import_tasks as tasks

    source_file = MagicMock(doc_format=None)  # obrazek itp.
    with patch("app.workers.tasks.document_tasks.parse_document_task") as parse:
        tasks._trigger_preprocessing(source_file, _project())

    parse.delay.assert_not_called()


def test_preprocessing_best_effort_nie_rzuca():
    from app.workers.tasks import jira_import_tasks as tasks

    source_file = MagicMock(doc_format="pdf", filename="spec.pdf")
    with patch(
        "app.workers.tasks.document_tasks.parse_document_task",
        MagicMock(delay=MagicMock(side_effect=RuntimeError("broker nie żyje"))),
    ):
        tasks._trigger_preprocessing(source_file, _project())  # połyka błąd


def test_zadanie_idzie_na_kolejke_sync():
    from app.workers.tasks import jira_import_tasks as tasks

    assert tasks.import_from_jira_task.queue == "sync"
    assert tasks.import_from_jira_task.name == "jira.import_requirements"


# ── zapis dokumentu do magazynu ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_document_importuje_istniejacy_modul():
    """Lazy import wskazywał nieistniejący ``app.core.minio_client``
    (2026-09-28, import padał dopiero na serwerze — wszystkie testy
    podstawiały _ensure_document/_persist_file_bytes i go nie dotykały).
    Patchujemy prawdziwy symbol, więc zły moduł pada już przy wywołaniu."""
    from app.workers.tasks import jira_import_tasks as tasks

    with patch("app.core.storage.upload_file") as upload:
        await tasks._upload_document("klucz/jira-QA.md", b"tresc")

    upload.assert_called_once()
    assert upload.call_args.args[0]  # nazwa bucketa z ustawień
    assert upload.call_args.args[3] == len(b"tresc")


@pytest.mark.asyncio
async def test_nieudany_zapis_dokumentu_nie_przerywa_importu():
    from app.workers.tasks import jira_import_tasks as tasks

    with patch("app.core.storage.upload_file", side_effect=RuntimeError("MinIO nie odpowiada")):
        await tasks._upload_document("klucz/jira-QA.md", b"tresc")  # połyka błąd
