"""Dwukierunkowa synchronizacja przypadków testowych z TMS — Story 8.11.

Story 8.8 i 8.9 wysyłały przypadki w jedną stronę. Tu dochodzi kierunek
powrotny, a wraz z nim pytanie, którego eksport nie musiał sobie zadawać:
co zrobić, gdy ten sam przypadek zmienił się po obu stronach.

Trzy decyzje kształtują ten moduł:

* **Push to eksport ograniczony do zmian.** Wysyłamy przypadki z
  ``updated_at`` nowszym niż ostatnia synchronizacja i korzystamy z
  gotowych eksporterów ze Story 8.8/8.9. Drugi mechanizm tworzenia
  przypadków w TMS rozjechałby się z pierwszym przy pierwszej zmianie
  mapowania pól.

* **Konflikt zapisujemy zawsze, nawet gdy strategia go rozstrzyga.**
  Przy ``last_write_wins`` przegrana wersja jest jedynym śladem po
  nadpisanych danych — bez niej analityk nie odtworzy, co zniknęło.

* **Jeden nieudany przebieg to nie awaria.** Dopiero trzy z rzędu wprowadzają
  stan ``degraded`` i powiadomienie, bo pojedynczy timeout zdarza się przy
  każdym wdrożeniu po stronie TMS-a.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.analysis_result import AnalysisResult
from app.models.integration import IntegrationConfig, SyncStatus
from app.models.sync_conflict import ConflictResolution, SyncConflict
from app.models.sync_state import (
    DEGRADED_AFTER_FAILURES,
    MIN_INTERVAL_MINUTES,
    ConflictStrategy,
    SyncDirection,
    SyncHealth,
    SyncState,
)
from app.models.test_case import TestCase, TestPriority
from app.services.export.jira_tms_service import XRAY_LABEL_PREFIX, ZEPHYR_TESTGEN_FIELD
from app.services.export.tms_common import steps_list
from app.services.export.tms_exporter import TESTGEN_ID_FIELD

logger = logging.getLogger(__name__)

SYNC_PROVIDERS = ("testrail", "xray", "zephyr")

# Pola przenoszone z TMS do TestGEN. Świadomie wąska lista: kod testu
# i metadane analizy powstają w TestGEN i nie mają odpowiednika w TMS-ie,
# więc ściąganie ich z powrotem mogłoby je tylko wymazać.
PULLED_FIELDS = ("title", "description", "priority", "steps", "expected_result")

_PRIORITY_FROM_TMS: dict[str, TestPriority] = {
    "CRITICAL": TestPriority.CRITICAL,
    "HIGH": TestPriority.HIGH,
    "MEDIUM": TestPriority.MEDIUM,
    "LOW": TestPriority.LOW,
    # Nazwy z domyślnej instalacji TestRaila.
    "MUST TEST": TestPriority.CRITICAL,
    "TEST IF TIME": TestPriority.LOW,
    "DON'T TEST": TestPriority.LOW,
    # Nazwy priorytetów Jiry.
    "HIGHEST": TestPriority.CRITICAL,
    "LOWEST": TestPriority.LOW,
}


# ── modele wyniku ───────────────────────────────────────────────────────────


@dataclass
class RemoteCase:
    """Przypadek po stronie TMS-a, sprowadzony do wspólnego kształtu."""

    testgen_id: str
    external_id: str
    title: str = ""
    updated_at: datetime | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    def as_snapshot(self) -> dict[str, Any]:
        return {
            "external_id": self.external_id,
            "title": self.title,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            **self.fields,
        }


@dataclass
class SyncOutcome:
    """Podsumowanie jednego przebiegu."""

    pushed: int = 0
    pulled: int = 0
    conflicts: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "SyncOutcome") -> "SyncOutcome":
        self.pushed += other.pushed
        self.pulled += other.pulled
        self.conflicts += other.conflicts
        self.skipped += other.skipped
        self.failed += other.failed
        self.errors.extend(other.errors)
        return self

    @property
    def status(self) -> SyncStatus:
        if self.failed and not (self.pushed or self.pulled):
            return SyncStatus.FAILED
        if self.failed or self.conflicts:
            return SyncStatus.PARTIAL
        return SyncStatus.SUCCESS

    def as_dict(self) -> dict[str, Any]:
        return {
            "pushed": self.pushed,
            "pulled": self.pulled,
            "conflicts": self.conflicts,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
            "status": self.status.value,
        }


# ── normalizacja odpowiedzi TMS ─────────────────────────────────────────────


def _as_datetime(value: Any) -> datetime | None:
    """Znaczniki czasu przychodzą jako liczba (TestRail) albo ISO (Jira)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        logger.warning("Nierozpoznany znacznik czasu z TMS: %r", value)
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _priority_from_tms(value: Any) -> TestPriority | None:
    if value in (None, ""):
        return None
    return _PRIORITY_FROM_TMS.get(str(value).strip().upper())


def remote_from_testrail(case: dict[str, Any]) -> RemoteCase | None:
    """Przypadek TestRaila → wspólny kształt; ``None`` gdy nie pochodzi z TestGEN."""
    marker = case.get(TESTGEN_ID_FIELD)
    if not marker:
        return None
    return RemoteCase(
        testgen_id=str(marker),
        external_id=str(case.get("id") or ""),
        title=str(case.get("title") or ""),
        updated_at=_as_datetime(case.get("updated_on")),
        fields={
            "description": str(case.get("custom_preconds") or ""),
            "steps": steps_list(case.get("custom_steps")),
            "expected_result": str(case.get("custom_expected") or ""),
            "priority_id": case.get("priority_id"),
        },
    )


def remote_from_xray(issue: dict[str, Any]) -> RemoteCase | None:
    """Zgłoszenie Jiry oznaczone etykietą TestGEN → wspólny kształt."""
    fields = issue.get("fields") or {}
    marker = next(
        (
            label.removeprefix(XRAY_LABEL_PREFIX)
            for label in (fields.get("labels") or [])
            if label.startswith(XRAY_LABEL_PREFIX)
        ),
        None,
    )
    if not marker:
        return None
    priority = fields.get("priority") or {}
    return RemoteCase(
        testgen_id=marker,
        external_id=str(issue.get("key") or ""),
        title=str(fields.get("summary") or ""),
        updated_at=_as_datetime(fields.get("updated")),
        fields={
            "description": str(fields.get("description") or ""),
            "priority": priority.get("name") if isinstance(priority, dict) else priority,
        },
    )


def remote_from_zephyr(case: dict[str, Any]) -> RemoteCase | None:
    """Przypadek Zephyra z polem własnym ``testgen_id`` → wspólny kształt."""
    marker = (case.get("customFields") or {}).get(ZEPHYR_TESTGEN_FIELD)
    if not marker:
        return None
    steps = [
        str((step or {}).get("description") or "")
        for step in ((case.get("testScript") or {}).get("steps") or [])
    ]
    return RemoteCase(
        testgen_id=str(marker),
        external_id=str(case.get("key") or ""),
        title=str(case.get("name") or ""),
        updated_at=_as_datetime(case.get("updatedOn") or case.get("lastModifiedOn")),
        fields={
            "description": str(case.get("objective") or ""),
            "steps": [step for step in steps if step],
            "priority": case.get("priorityName") or case.get("priority"),
        },
    )


# ── decyzje o konflikcie ────────────────────────────────────────────────────


def detect_conflict(
    local_updated: datetime | None,
    remote: RemoteCase,
    last_sync_at: datetime | None,
) -> bool:
    """Konflikt = obie strony zmienione po ostatniej synchronizacji (AC4).

    Pierwszy przebieg (``last_sync_at`` puste) nie może dać konfliktu:
    nie ma punktu odniesienia, względem którego „obie strony" cokolwiek
    znaczą — wtedy TMS jest po prostu nowszym albo starszym źródłem.
    """
    if last_sync_at is None:
        return False
    return bool(
        local_updated
        and remote.updated_at
        and local_updated > last_sync_at
        and remote.updated_at > last_sync_at
    )


def choose_winner(local_updated: datetime | None, remote: RemoteCase) -> str:
    """Strategia ``last_write_wins``: nowszy ``updated_at`` wygrywa (AC4)."""
    if remote.updated_at is None:
        return "testgen"
    if local_updated is None:
        return "tms"
    return "tms" if remote.updated_at > local_updated else "testgen"


def snapshot_test_case(test_case: TestCase) -> dict[str, Any]:
    """Wersja przypadku z TestGEN zapisywana przy konflikcie."""
    return {
        "id": str(test_case.id),
        "title": test_case.title or "",
        "description": test_case.description or "",
        "priority": getattr(test_case.priority, "value", test_case.priority),
        "steps": steps_list(test_case.steps),
        "expected_result": test_case.expected_result or "",
        "updated_at": test_case.updated_at.isoformat() if test_case.updated_at else None,
    }


def apply_remote(test_case: TestCase, remote: RemoteCase) -> list[str]:
    """Wnosi zmiany z TMS do przypadku. Zwraca nazwy zmienionych pól.

    Puste pole po stronie TMS-a nie kasuje wartości w TestGEN: większość
    instancji nie wypełnia wszystkich pól, a synchronizacja nie może być
    powodem utraty opisu, którego nikt nie tknął.
    """
    changed: list[str] = []

    if remote.title and remote.title != test_case.title:
        test_case.title = remote.title[:500]
        changed.append("title")

    description = str(remote.fields.get("description") or "")
    if description and description != (test_case.description or ""):
        test_case.description = description
        changed.append("description")

    expected = str(remote.fields.get("expected_result") or "")
    if expected and expected != (test_case.expected_result or ""):
        test_case.expected_result = expected
        changed.append("expected_result")

    steps = remote.fields.get("steps") or []
    if steps and steps != steps_list(test_case.steps):
        test_case.steps = {"items": [str(step) for step in steps]}
        changed.append("steps")

    priority = _priority_from_tms(remote.fields.get("priority"))
    if priority is not None and priority != test_case.priority:
        test_case.priority = priority
        changed.append("priority")

    return changed


# ── konfiguracja ────────────────────────────────────────────────────────────


async def _get_integration(
    db: AsyncSession, integration_id: uuid.UUID, tenant_id: uuid.UUID
) -> IntegrationConfig:
    integration = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.id == integration_id,
                IntegrationConfig.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if integration is None:
        raise NotFoundError("Integracja nie została znaleziona")
    provider = getattr(integration.provider, "value", integration.provider)
    if provider not in SYNC_PROVIDERS:
        raise ValidationError(
            f"Synchronizacja dwukierunkowa nie jest dostępna dla dostawcy {provider}"
        )
    return integration


async def get_sync_state(
    db: AsyncSession, integration_id: uuid.UUID, tenant_id: uuid.UUID
) -> SyncState:
    state = (
        await db.execute(
            select(SyncState).where(
                SyncState.integration_id == integration_id,
                SyncState.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if state is None:
        raise NotFoundError("Synchronizacja nie została skonfigurowana dla tej integracji")
    return state


async def configure_sync(
    db: AsyncSession,
    integration_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    direction: SyncDirection,
    interval_minutes: int,
    conflict_strategy: ConflictStrategy,
) -> SyncState:
    """Tworzy albo nadpisuje konfigurację synchronizacji (AC1)."""
    if interval_minutes < MIN_INTERVAL_MINUTES:
        raise ValidationError(
            f"Odstęp synchronizacji nie może być krótszy niż {MIN_INTERVAL_MINUTES} min"
        )

    integration = await _get_integration(db, integration_id, tenant_id)
    state = (
        await db.execute(
            select(SyncState).where(
                SyncState.integration_id == integration_id,
                SyncState.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()

    if state is None:
        # Wartości początkowe wypisane wprost, a nie zostawione domyślnym
        # wartościom kolumn: te nadaje dopiero INSERT, więc obiekt zwrócony
        # przed zapisem miałby puste pola tam, gdzie odpowiedź API oczekuje
        # liczby albo flagi.
        state = SyncState(
            tenant_id=tenant_id,
            integration_id=integration_id,
            project_id=integration.project_id,
            provider=getattr(integration.provider, "value", integration.provider),
            is_active=False,
            health=SyncHealth.ACTIVE,
            consecutive_failures=0,
            synced_count=0,
        )
        db.add(state)

    state.direction = direction
    state.interval_minutes = interval_minutes
    state.conflict_strategy = conflict_strategy
    await db.flush()
    return state


async def set_active(
    db: AsyncSession, integration_id: uuid.UUID, tenant_id: uuid.UUID, active: bool
) -> SyncState:
    state = await get_sync_state(db, integration_id, tenant_id)
    state.is_active = active
    if active:
        # Włączenie po awarii zaczyna licznik od zera — inaczej pierwsza
        # potknięta próba od razu wracałaby do stanu ``degraded``.
        state.consecutive_failures = 0
        state.health = SyncHealth.ACTIVE
        state.last_error = None
    await db.flush()
    return state


def sync_status_view(state: SyncState, pending_conflicts: int = 0) -> dict[str, Any]:
    """Kształt odpowiedzi ekranu synchronizacji (AC5)."""
    return {
        "id": state.id,
        "integration_id": state.integration_id,
        "project_id": state.project_id,
        "provider": state.provider,
        "direction": getattr(state.direction, "value", state.direction),
        "conflict_strategy": getattr(state.conflict_strategy, "value", state.conflict_strategy),
        "interval_minutes": state.interval_minutes,
        "is_active": state.is_active,
        "health": getattr(state.health, "value", state.health),
        "last_sync_at": state.last_sync_at,
        "last_sync_status": (
            getattr(state.last_sync_status, "value", state.last_sync_status)
            if state.last_sync_status
            else None
        ),
        "last_error": state.last_error,
        "consecutive_failures": state.consecutive_failures,
        "synced_count": state.synced_count,
        "pending_conflicts": pending_conflicts,
        "next_sync_at": next_run_at(state),
    }


def next_run_at(state: SyncState) -> datetime | None:
    if not state.is_active:
        return None
    if state.last_sync_at is None:
        return datetime.now(UTC)
    return state.last_sync_at + _interval(state)


def _interval(state: SyncState):
    from datetime import timedelta

    return timedelta(minutes=max(state.interval_minutes, MIN_INTERVAL_MINUTES))


def is_due(state: SyncState, now: datetime | None = None) -> bool:
    """Czy przebieg jest zaległy. Używane przez beat i przy ręcznym wyzwoleniu."""
    if not state.is_active:
        return False
    if state.last_sync_at is None:
        return True
    return (now or datetime.now(UTC)) >= state.last_sync_at + _interval(state)


async def due_sync_states(db: AsyncSession, now: datetime | None = None) -> list[SyncState]:
    """Aktywne synchronizacje z zaległym terminem — przez wszystkie firmy.

    Filtr po ``is_active`` robi baza, a porównanie terminu Python: odstęp
    jest kolumną, więc wyrażenie ``last_sync_at + interval`` i tak nie
    skorzystałoby z indeksu.
    """
    rows = (
        await db.execute(select(SyncState).where(SyncState.is_active.is_(True)))
    ).scalars().all()
    moment = now or datetime.now(UTC)
    return [state for state in rows if is_due(state, moment)]


# ── zdrowie synchronizacji ──────────────────────────────────────────────────


def record_success(state: SyncState, outcome: SyncOutcome, finished_at: datetime) -> None:
    state.last_sync_at = finished_at
    state.last_sync_status = outcome.status
    state.last_error = "; ".join(outcome.errors)[:2000] or None
    state.synced_count = outcome.pushed + outcome.pulled
    state.consecutive_failures = 0
    state.health = SyncHealth.ACTIVE


def record_failure(state: SyncState, error: str, finished_at: datetime) -> bool:
    """Zapisuje nieudany przebieg. Zwraca ``True``, gdy stan właśnie zdegradował.

    ``last_sync_at`` przesuwamy mimo porażki — inaczej zaległa synchronizacja
    byłaby podejmowana przy każdym przebiegu beat-a i niedostępny TMS
    dostawałby lawinę żądań zamiast jednej próby na odstęp.
    """
    state.last_sync_at = finished_at
    state.last_sync_status = SyncStatus.FAILED
    state.last_error = error[:2000]
    state.consecutive_failures += 1
    just_degraded = (
        state.consecutive_failures >= DEGRADED_AFTER_FAILURES
        and state.health is not SyncHealth.DEGRADED
    )
    if state.consecutive_failures >= DEGRADED_AFTER_FAILURES:
        state.health = SyncHealth.DEGRADED
    return just_degraded


# ── przebieg synchronizacji ─────────────────────────────────────────────────


async def changed_test_cases(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    since: datetime | None,
) -> list[TestCase]:
    """Przypadki projektu zmienione po ``since`` (albo wszystkie przy pierwszym przebiegu)."""
    stmt = select(TestCase).where(
        TestCase.tenant_id == tenant_id,
        # TestCase nie ma ``project_id`` — wiąże się z projektem przez AnalysisResult.
        TestCase.analysis_result_id.in_(
            select(AnalysisResult.id).where(AnalysisResult.project_id == project_id)
        ),
    )
    if since is not None:
        # Nowe przypadki mają puste ``updated_at`` — liczy się wtedy data utworzenia.
        stmt = stmt.where(
            (TestCase.updated_at > since)
            | (TestCase.updated_at.is_(None) & (TestCase.created_at > since))
        )
    return list((await db.execute(stmt)).scalars().all())


def local_updated_at(test_case: TestCase) -> datetime | None:
    return test_case.updated_at or test_case.created_at


async def record_conflict(
    db: AsyncSession,
    state: SyncState,
    test_case: TestCase,
    remote: RemoteCase,
    resolution: ConflictResolution,
) -> SyncConflict:
    conflict = SyncConflict(
        tenant_id=state.tenant_id,
        sync_state_id=state.id,
        test_case_id=test_case.id,
        tms_test_id=remote.external_id,
        testgen_version=snapshot_test_case(test_case),
        tms_version=remote.as_snapshot(),
        resolution=resolution,
        resolved_at=datetime.now(UTC) if resolution is not ConflictResolution.PENDING else None,
    )
    db.add(conflict)
    return conflict


async def resolve_conflict(
    db: AsyncSession,
    conflict_id: uuid.UUID,
    tenant_id: uuid.UUID,
    resolution: ConflictResolution,
    user_id: uuid.UUID,
) -> SyncConflict:
    """Ręczne rozstrzygnięcie konfliktu (AC4).

    ``testgen_wins`` nie zmienia niczego lokalnie — wersja TestGEN już tam
    jest, a do TMS-a trafi przy najbliższym pushu. ``tms_wins`` wnosi
    zapamiętaną wersję TMS-a do przypadku.
    """
    if resolution is ConflictResolution.PENDING:
        raise ValidationError("Rozstrzygnięcie nie może przywrócić stanu „oczekuje”")

    conflict = (
        await db.execute(
            select(SyncConflict).where(
                SyncConflict.id == conflict_id,
                SyncConflict.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if conflict is None:
        raise NotFoundError("Konflikt nie został znaleziony")
    if conflict.resolution is not ConflictResolution.PENDING:
        raise ValidationError("Konflikt został już rozstrzygnięty")

    if resolution is ConflictResolution.TMS_WINS:
        test_case = (
            await db.execute(
                select(TestCase).where(
                    TestCase.id == conflict.test_case_id,
                    TestCase.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if test_case is None:
            raise NotFoundError("Przypadek testowy nie istnieje")
        apply_remote(test_case, _remote_from_snapshot(conflict.tms_version))

    conflict.resolution = resolution
    conflict.resolved_at = datetime.now(UTC)
    conflict.resolved_by = user_id
    await db.flush()
    return conflict


def _remote_from_snapshot(snapshot: dict[str, Any]) -> RemoteCase:
    data = dict(snapshot or {})
    return RemoteCase(
        testgen_id="",
        external_id=str(data.pop("external_id", "")),
        title=str(data.pop("title", "")),
        updated_at=_as_datetime(data.pop("updated_at", None)),
        fields=data,
    )


# ── odczyt z TMS ────────────────────────────────────────────────────────────


async def fetch_remote_index(
    provider: str, client: Any, settings: dict[str, Any]
) -> dict[str, RemoteCase]:
    """Indeks przypadków TMS pochodzących z TestGEN, po identyfikatorze przypadku.

    Wszystkie trzy API pobieramy w całości i filtrujemy po swojej stronie.
    Parametry „zmienione po" różnią się między nimi na tyle (TestRail liczy
    sekundy uniksowe, Jira przyjmuje JQL, Zephyr własny format), że jeden
    wspólny filtr i tak trzeba by składać trzy razy — a pełny odczyt to i tak
    jedno lub kilka żądań dzięki stronicowaniu po stronie klientów.
    """
    if provider == "xray":
        issues = await client.xray_find_all_testgen(str(settings["jira_project_key"]))
        remotes = (remote_from_xray(issue) for issue in issues.values())
    elif provider == "zephyr":
        cases = await client.zephyr_find_all_testgen(str(settings["jira_project_key"]))
        remotes = (remote_from_zephyr(case) for case in cases.values())
    else:
        cases = await client.get_cases(
            int(settings["testrail_project_id"]), suite_id=settings.get("suite_id")
        )
        remotes = (remote_from_testrail(case) for case in cases)

    return {remote.testgen_id: remote for remote in remotes if remote is not None}


# ── kierunek: TestGEN → TMS ─────────────────────────────────────────────────


async def run_push_sync(
    db: AsyncSession,
    state: SyncState,
    exporter: Any,
    *,
    since: datetime | None = None,
) -> SyncOutcome:
    """Wysyła do TMS-a przypadki zmienione od ostatniej synchronizacji (AC2)."""
    from app.services.export.tms_exporter import rows_from_test_cases

    outcome = SyncOutcome()
    moment = since if since is not None else state.last_sync_at
    test_cases = await changed_test_cases(db, state.tenant_id, state.project_id, moment)
    if not test_cases:
        return outcome

    result = await exporter.export(rows_from_test_cases(test_cases))
    outcome.pushed = result.created + result.updated
    outcome.failed = result.failed
    outcome.errors = [
        f"{item.title}: {item.error}" for item in result.items if item.action == "failed"
    ][:20]

    link_test_cases(test_cases, result.items)
    return outcome


def link_test_cases(test_cases: list[TestCase], items: list[Any]) -> int:
    """Zapisuje na przypadkach ich identyfikator po stronie TMS (AC5).

    Bez tego lista przypadków nie miałaby skąd wziąć plakietki „zsynchronizowany
    z TestRail #1234" — identyfikator zna wyłącznie odpowiedź eksportu.
    """
    by_id = {str(tc.id): tc for tc in test_cases}
    moment = datetime.now(UTC)
    linked = 0
    for item in items:
        if getattr(item, "action", "") == "failed":
            continue
        test_case = by_id.get(str(getattr(item, "test_case_id", "")))
        if test_case is None:
            continue
        external = getattr(item, "external_key", None) or getattr(item, "testrail_case_id", None)
        if external is None:
            continue
        test_case.tms_external_id = str(external)[:64]
        test_case.tms_synced_at = moment
        linked += 1
    return linked


# ── kierunek: TMS → TestGEN ─────────────────────────────────────────────────


async def run_pull_sync(
    db: AsyncSession,
    state: SyncState,
    remote_index: dict[str, RemoteCase],
) -> SyncOutcome:
    """Wnosi zmiany z TMS-a do TestGEN, wykrywając konflikty (AC3, AC4)."""
    outcome = SyncOutcome()
    if not remote_index:
        return outcome

    test_cases = {
        str(tc.id): tc
        for tc in await changed_test_cases(db, state.tenant_id, state.project_id, None)
    }

    for testgen_id, remote in remote_index.items():
        test_case = test_cases.get(testgen_id)
        if test_case is None:
            # Przypadek skasowany w TestGEN albo należący do innego projektu —
            # nie tworzymy go z powrotem, bo kierunek TMS → TestGEN nie zna
            # wyniku analizy, do którego musiałby się podpiąć.
            outcome.skipped += 1
            continue

        local_updated = local_updated_at(test_case)
        conflicted = detect_conflict(local_updated, remote, state.last_sync_at)
        # Brak znacznika czasu po stronie TMS-a traktujemy jak zmianę: lepiej
        # porównać pola (``apply_remote`` i tak nic nie zmieni, gdy są równe)
        # niż przeoczyć edycję w instancji, która znacznika nie wystawia.
        remote_changed = (
            state.last_sync_at is None
            or remote.updated_at is None
            or remote.updated_at > state.last_sync_at
        )
        if not conflicted and not remote_changed:
            outcome.skipped += 1
            continue

        if conflicted:
            outcome.conflicts += 1
            if state.conflict_strategy is ConflictStrategy.MANUAL:
                await record_conflict(db, state, test_case, remote, ConflictResolution.PENDING)
                outcome.skipped += 1
                continue

            winner = choose_winner(local_updated, remote)
            await record_conflict(
                db,
                state,
                test_case,
                remote,
                ConflictResolution.TMS_WINS
                if winner == "tms"
                else ConflictResolution.TESTGEN_WINS,
            )
            if winner == "testgen":
                # Wersja TestGEN wygrywa — trafi do TMS-a przy najbliższym pushu.
                continue

        # Powiązanie odświeżamy także wtedy, gdy nic się nie zmieniło:
        # plakietka na liście przypadków ma mówić „widzieliśmy się", a nie
        # „ostatnio coś przepisaliśmy".
        test_case.tms_external_id = remote.external_id[:64] or test_case.tms_external_id
        test_case.tms_synced_at = datetime.now(UTC)

        if apply_remote(test_case, remote):
            outcome.pulled += 1
        else:
            outcome.skipped += 1

    await db.flush()
    return outcome
