"""Orkiestracja eksportu przypadków testowych do TMS — Epic 8, Story 8.8.

Klient (``testrail_service``) wie, jak rozmawiać z API; ten moduł decyduje,
co utworzyć, co zaktualizować i co pominąć.

Trzy decyzje kształtują ten kod:

* **Deduplikacja po ``custom_testgen_id``.** Identyfikator TestGEN zapisany
  w polu własnym TestRaila jest jedynym pewnym powiązaniem — tytuł może się
  zmienić, a wtedy ponowny eksport zrobiłby duplikat zamiast aktualizacji.
* **Jeden odczyt przypadków na eksport.** Szukanie po ``custom_testgen_id``
  osobnym żądaniem dla każdego przypadku to N wywołań przy limicie
  ~1 żądanie/s; zamiast tego pobieramy je raz i budujemy indeks w pamięci.
* **Błąd pojedynczego przypadku nie przerywa eksportu.** Przy setce testów
  jeden odrzucony przez walidację TestRaila nie może unieważnić pozostałych —
  raport wymienia go osobno.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.export.jira_tms_service import ZEPHYR_TESTGEN_FIELD, testgen_label
from app.services.export.testrail_service import TestRailClient, TestRailError
from app.services.export.tms_common import as_text, steps_list, test_case_row

logger = logging.getLogger(__name__)

# Pole własne TestRaila wiążące przypadek z TestGEN. Musi istnieć w projekcie
# docelowym (Administration → Customizations) — bez niego deduplikacja nie ma
# się o co oprzeć i każdy eksport tworzyłby duplikaty.
TESTGEN_ID_FIELD = "custom_testgen_id"

# Domyślne mapowanie priorytetów TestGEN → identyfikatory TestRaila.
# 1 = Low … 4 = Critical w domyślnej konfiguracji TestRaila.
DEFAULT_PRIORITY_MAP: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}
DEFAULT_PRIORITY_ID = 2

# Domyślne mapowanie typów. Identyfikatory zależą od instancji, więc to tylko
# punkt wyjścia — użytkownik nadpisuje je w konfiguracji integracji (AC4).
DEFAULT_TYPE_MAP: dict[str, int] = {
    "FUNCTIONAL": 7,
    "REGRESSION": 9,
    "SECURITY": 12,
    "PERFORMANCE": 5,
    "ACCESSIBILITY": 10,
}
DEFAULT_TYPE_ID = 7

_DEFAULT_SECTION_NAME = "TestGEN"


@dataclass
class ExportItemResult:
    test_case_id: str
    title: str
    action: str  # created | updated | failed
    # TestRail adresuje przypadki liczbą, Jira kluczem tekstowym — stąd dwa pola.
    testrail_case_id: int | None = None
    external_key: str | None = None
    error: str | None = None


@dataclass
class ExportResult:
    created: int = 0
    updated: int = 0
    failed: int = 0
    items: list[ExportItemResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated + self.failed

    def as_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "failed": self.failed,
            "total": self.total,
            "items": [
                {
                    "test_case_id": item.test_case_id,
                    "title": item.title,
                    "action": item.action,
                    "testrail_case_id": item.testrail_case_id,
                    "external_key": item.external_key,
                    "error": item.error,
                }
                for item in self.items
            ],
        }


def _int_map(raw: Any, default: dict[str, int]) -> dict[str, int]:
    """Normalizuje mapowanie z konfiguracji (klucze bywają w dowolnej wielkości liter)."""
    if not isinstance(raw, dict) or not raw:
        return dict(default)
    normalized: dict[str, int] = dict(default)
    for key, value in raw.items():
        try:
            normalized[str(key).upper()] = int(value)
        except (TypeError, ValueError):
            logger.warning("Pomijam nieprawidłowe mapowanie %s → %r", key, value)
    return normalized


def build_testrail_case(row: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Zamienia znormalizowany przypadek TestGEN na ciało żądania TestRaila (AC2/AC4)."""
    config = config or {}
    priority_map = _int_map(config.get("priority_map"), DEFAULT_PRIORITY_MAP)
    type_map = _int_map(config.get("type_map"), DEFAULT_TYPE_MAP)
    field_mapping = config.get("field_mapping") or {}

    priority = (row.get("priority") or "").upper()
    test_type = (row.get("type") or "").upper()

    payload: dict[str, Any] = {
        "title": (row.get("title") or "").strip() or "Przypadek testowy bez tytułu",
        "priority_id": priority_map.get(priority, DEFAULT_PRIORITY_ID),
        "type_id": type_map.get(test_type, DEFAULT_TYPE_ID),
        "custom_preconds": as_text(row.get("preconditions")),
        "custom_expected": as_text(row.get("expected_result")),
        # Kroki w formacie „separated" — TestRail renderuje je jako tabelę,
        # a nie jeden blok tekstu.
        "custom_steps_separated": [
            {"content": step, "expected": ""} for step in steps_list(row.get("steps"))
        ],
        TESTGEN_ID_FIELD: row.get("id", ""),
    }

    # Pola dodatkowe wskazane przez użytkownika: {"custom_moje_pole": "source_function"}
    for testrail_field, testgen_field in field_mapping.items():
        if not testrail_field.startswith("custom_"):
            continue
        payload[testrail_field] = as_text(row.get(testgen_field, ""))

    return payload


def section_name_for(row: dict[str, Any]) -> str:
    """Nazwa sekcji: moduł przypadku, a w jego braku wspólna sekcja TestGEN."""
    return (row.get("module") or "").strip() or _DEFAULT_SECTION_NAME


def index_by_testgen_id(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Indeks istniejących przypadków po ``custom_testgen_id`` (AC3)."""
    index: dict[str, dict[str, Any]] = {}
    for case in cases:
        marker = case.get(TESTGEN_ID_FIELD)
        if marker:
            index[str(marker)] = case
    return index


class TestRailExporter:
    """Jeden przebieg eksportu do jednego projektu TestRail."""

    def __init__(self, client: TestRailClient, config: dict[str, Any]) -> None:
        self.client = client
        self.config = config or {}
        self.project_id = int(self.config["testrail_project_id"])
        self.suite_id = self.config.get("suite_id")
        self._sections: dict[str, int] = {}

    async def _load_sections(self) -> None:
        sections = await self.client.get_sections(self.project_id, suite_id=self.suite_id)
        self._sections = {
            str(s.get("name", "")).strip().lower(): s["id"] for s in sections if s.get("id")
        }

    async def _section_id_for(self, name: str) -> int:
        """Identyfikator sekcji, zakładając ją przy pierwszym użyciu (AC2)."""
        key = name.strip().lower()
        if key in self._sections:
            return self._sections[key]

        created = await self.client.create_section(
            self.project_id, name, suite_id=self.suite_id
        )
        section_id = created.get("id")
        if not section_id:
            raise TestRailError(f"TestRail nie zwrócił identyfikatora sekcji „{name}”")
        self._sections[key] = section_id
        return section_id

    async def export(self, rows: list[dict[str, Any]], progress=None) -> ExportResult:
        """Eksportuje przypadki, aktualizując już istniejące (AC2/AC3).

        ``progress`` (opcjonalne) dostaje ``(zrobione, wszystkie)`` po każdym
        przypadku — eksport setki testów przy limicie tempa trwa minuty.
        """
        result = ExportResult()
        if not rows:
            return result

        await self._load_sections()
        existing = index_by_testgen_id(
            await self.client.get_cases(self.project_id, suite_id=self.suite_id)
        )

        for done, row in enumerate(rows, start=1):
            test_case_id = str(row.get("id", ""))
            title = row.get("title") or ""
            try:
                payload = build_testrail_case(row, self.config)
                match = existing.get(test_case_id)

                if match:
                    updated = await self.client.update_case(match["id"], payload)
                    result.updated += 1
                    result.items.append(
                        ExportItemResult(
                            test_case_id=test_case_id,
                            title=title,
                            action="updated",
                            testrail_case_id=updated.get("id") or match["id"],
                        )
                    )
                else:
                    section_id = await self._section_id_for(section_name_for(row))
                    created = await self.client.add_case(section_id, payload)
                    result.created += 1
                    result.items.append(
                        ExportItemResult(
                            test_case_id=test_case_id,
                            title=title,
                            action="created",
                            testrail_case_id=created.get("id"),
                        )
                    )
            except Exception as exc:
                # Jeden odrzucony przypadek nie może unieważnić pozostałych.
                logger.warning("Eksport przypadku %s nie powiódł się: %s", test_case_id, exc)
                result.failed += 1
                result.items.append(
                    ExportItemResult(
                        test_case_id=test_case_id,
                        title=title,
                        action="failed",
                        error=str(exc)[:500],
                    )
                )

            if progress is not None:
                progress(done, len(rows))

        return result


def rows_from_test_cases(test_cases: list[Any]) -> list[dict[str, Any]]:
    """Normalizuje modele TestCase do słowników używanych przez eksport."""
    return [test_case_row(tc) for tc in test_cases]


# ── Story 8.9: eksport do Jira Xray i Zephyr Scale ──────────────────────────

# Domyślne mapowanie priorytetów TestGEN → nazwy priorytetów Jiry.
# Jira adresuje je nazwą, nie liczbą (inaczej niż TestRail).
DEFAULT_JIRA_PRIORITY_MAP: dict[str, str] = {
    "CRITICAL": "Highest",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "LOW": "Low",
}

# Typ testu trafia do etykiety, bo komponenty Jiry trzeba wcześniej założyć
# w projekcie, a etykiety powstają same.
DEFAULT_JIRA_TYPE_LABELS: dict[str, str] = {
    "FUNCTIONAL": "typ-funkcjonalny",
    "REGRESSION": "typ-regresyjny",
    "SECURITY": "typ-bezpieczenstwa",
    "PERFORMANCE": "typ-wydajnosciowy",
    "ACCESSIBILITY": "typ-dostepnosci",
}

_ZEPHYR_DEFAULT_FOLDER = "/TestGEN"


def _str_map(raw: Any, default: dict[str, str]) -> dict[str, str]:
    """Normalizuje mapowanie tekstowe z konfiguracji (klucze bez względu na wielkość liter)."""
    if not isinstance(raw, dict) or not raw:
        return dict(default)
    normalized = dict(default)
    for key, value in raw.items():
        if value is None or str(value).strip() == "":
            continue
        normalized[str(key).upper()] = str(value)
    return normalized


def build_xray_test(row: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Zamienia przypadek TestGEN na test w formacie importu Xraya (AC2)."""
    config = config or {}
    priority_map = _str_map(config.get("jira_priority_map"), DEFAULT_JIRA_PRIORITY_MAP)
    type_labels = _str_map(config.get("jira_type_labels"), DEFAULT_JIRA_TYPE_LABELS)

    labels = [testgen_label(str(row.get("id", "")))]
    type_label = type_labels.get((row.get("type") or "").upper())
    if type_label:
        labels.append(type_label)

    steps = [
        {"action": step, "data": "", "result": ""} for step in steps_list(row.get("steps"))
    ]
    # Oczekiwany rezultat opisuje cały test, nie pojedynczy krok — dopinamy go
    # do ostatniego, żeby nie zgubić go przy imporcie.
    if steps and row.get("expected_result"):
        steps[-1]["result"] = as_text(row.get("expected_result"))

    test: dict[str, Any] = {
        "testtype": "Manual",
        "fields": {
            "summary": (row.get("title") or "").strip() or "Przypadek testowy bez tytułu",
            "description": as_text(row.get("description")) or as_text(row.get("preconditions")),
            "priority": {"name": priority_map.get((row.get("priority") or "").upper(), "Medium")},
            "labels": labels,
        },
        "steps": steps,
    }

    linked_issue = (config.get("linked_issue") or "").strip()
    if linked_issue:
        test["xray_test_sets"] = []
        test["linked_issue"] = linked_issue
    return test


def build_xray_update_fields(
    row: dict[str, Any], existing_labels: list[str], config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Pola do aktualizacji istniejącego zgłoszenia Xray (AC4).

    Etykiety scalamy z istniejącymi: zespół mógł dodać własne, a nadpisanie
    listy skasowałoby je przy każdym eksporcie.
    """
    config = config or {}
    priority_map = _str_map(config.get("jira_priority_map"), DEFAULT_JIRA_PRIORITY_MAP)
    type_labels = _str_map(config.get("jira_type_labels"), DEFAULT_JIRA_TYPE_LABELS)

    labels = set(existing_labels or [])
    labels.add(testgen_label(str(row.get("id", ""))))
    type_label = type_labels.get((row.get("type") or "").upper())
    if type_label:
        labels.add(type_label)

    return {
        "summary": (row.get("title") or "").strip() or "Przypadek testowy bez tytułu",
        "description": as_text(row.get("description")) or as_text(row.get("preconditions")),
        "priority": {"name": priority_map.get((row.get("priority") or "").upper(), "Medium")},
        "labels": sorted(labels),
    }


def build_zephyr_testcase(
    row: dict[str, Any],
    project_key: str,
    folder: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Zamienia przypadek TestGEN na test w formacie Zephyr Scale (AC3)."""
    config = config or {}
    priority_map = _str_map(config.get("jira_priority_map"), DEFAULT_JIRA_PRIORITY_MAP)

    steps = [
        {"description": step, "testData": "", "expectedResult": ""}
        for step in steps_list(row.get("steps"))
    ]
    if steps and row.get("expected_result"):
        steps[-1]["expectedResult"] = as_text(row.get("expected_result"))

    payload: dict[str, Any] = {
        "projectKey": project_key,
        "name": (row.get("title") or "").strip() or "Przypadek testowy bez tytułu",
        "objective": as_text(row.get("description")),
        "precondition": as_text(row.get("preconditions")),
        "priority": priority_map.get((row.get("priority") or "").upper(), "Medium"),
        "status": "Draft",
        "folder": folder or _ZEPHYR_DEFAULT_FOLDER,
        "testScript": {"type": "STEP_BY_STEP", "steps": steps},
        "customFields": {ZEPHYR_TESTGEN_FIELD: str(row.get("id", ""))},
    }
    return payload


def zephyr_folder_for(row: dict[str, Any]) -> str:
    """Ścieżka folderu Zephyra: moduł przypadku pod wspólnym korzeniem."""
    module = (row.get("module") or "").strip()
    return f"{_ZEPHYR_DEFAULT_FOLDER}/{module}" if module else _ZEPHYR_DEFAULT_FOLDER


class XrayExporter:
    """Jeden przebieg eksportu do projektu Jiry z wtyczką Xray."""

    def __init__(self, client, config: dict[str, Any]) -> None:
        self.client = client
        self.config = config or {}
        self.project_key = str(self.config["jira_project_key"])

    async def export(self, rows: list[dict[str, Any]], progress=None) -> ExportResult:
        result = ExportResult()
        if not rows:
            return result

        existing = await self.client.xray_find_all_testgen(self.project_key)
        linked_issue = (self.config.get("linked_issue") or "").strip()

        for done, row in enumerate(rows, start=1):
            test_case_id = str(row.get("id", ""))
            title = row.get("title") or ""
            try:
                match = existing.get(test_case_id)
                if match:
                    fields = build_xray_update_fields(
                        row, (match.get("fields") or {}).get("labels") or [], self.config
                    )
                    await self.client.xray_update_test(match["key"], fields)
                    result.updated += 1
                    result.items.append(
                        ExportItemResult(
                            test_case_id=test_case_id,
                            title=title,
                            action="updated",
                            external_key=match["key"],
                        )
                    )
                else:
                    test = build_xray_test(row, self.config)
                    test["fields"]["project"] = {"key": self.project_key}
                    response = await self.client.xray_import_tests([test])
                    key = _first_imported_key(response)
                    if key and linked_issue:
                        # Powiązanie z wymaganiem jest opcjonalne — jego brak
                        # nie może unieważnić utworzonego testu.
                        try:
                            await self.client.xray_link_to_requirement(key, linked_issue)
                        except Exception as exc:
                            logger.warning("Nie udało się powiązać %s z %s: %s", key, linked_issue, exc)
                    result.created += 1
                    result.items.append(
                        ExportItemResult(
                            test_case_id=test_case_id,
                            title=title,
                            action="created",
                            external_key=key,
                        )
                    )
            except Exception as exc:
                logger.warning("Eksport przypadku %s do Xray nie powiódł się: %s", test_case_id, exc)
                result.failed += 1
                result.items.append(
                    ExportItemResult(
                        test_case_id=test_case_id, title=title, action="failed", error=str(exc)[:500]
                    )
                )

            if progress is not None:
                progress(done, len(rows))

        return result


class ZephyrExporter:
    """Jeden przebieg eksportu do projektu Jiry z wtyczką Zephyr Scale."""

    def __init__(self, client, config: dict[str, Any]) -> None:
        self.client = client
        self.config = config or {}
        self.project_key = str(self.config["jira_project_key"])
        self._folders: set[str] = set()

    async def _ensure_folder(self, path: str) -> str:
        """Zakłada folder przy pierwszym użyciu; istniejący zostawia w spokoju."""
        if path in self._folders:
            return path
        try:
            await self.client.zephyr_create_folder(self.project_key, path)
        except Exception as exc:
            # Zephyr odrzuca duplikat nazwy — to znaczy, że folder już jest.
            logger.info("Folder %s prawdopodobnie już istnieje: %s", path, exc)
        self._folders.add(path)
        return path

    async def export(self, rows: list[dict[str, Any]], progress=None) -> ExportResult:
        result = ExportResult()
        if not rows:
            return result

        existing = await self.client.zephyr_find_all_testgen(self.project_key)
        for folder in {f.get("name") for f in await self.client.zephyr_get_folders(self.project_key)}:
            if folder:
                self._folders.add(str(folder))

        linked_issue = (self.config.get("linked_issue") or "").strip()

        for done, row in enumerate(rows, start=1):
            test_case_id = str(row.get("id", ""))
            title = row.get("title") or ""
            try:
                folder = await self._ensure_folder(zephyr_folder_for(row))
                payload = build_zephyr_testcase(row, self.project_key, folder, self.config)
                match = existing.get(test_case_id)

                if match:
                    await self.client.zephyr_update_testcase(match["key"], payload)
                    result.updated += 1
                    result.items.append(
                        ExportItemResult(
                            test_case_id=test_case_id,
                            title=title,
                            action="updated",
                            external_key=match["key"],
                        )
                    )
                else:
                    created = await self.client.zephyr_create_testcase(payload)
                    key = created.get("key")
                    if key and linked_issue:
                        try:
                            await self.client.zephyr_link_issue(key, linked_issue)
                        except Exception as exc:
                            logger.warning("Nie udało się powiązać %s z %s: %s", key, linked_issue, exc)
                    result.created += 1
                    result.items.append(
                        ExportItemResult(
                            test_case_id=test_case_id, title=title, action="created", external_key=key
                        )
                    )
            except Exception as exc:
                logger.warning("Eksport przypadku %s do Zephyra nie powiódł się: %s", test_case_id, exc)
                result.failed += 1
                result.items.append(
                    ExportItemResult(
                        test_case_id=test_case_id, title=title, action="failed", error=str(exc)[:500]
                    )
                )

            if progress is not None:
                progress(done, len(rows))

        return result


def _first_imported_key(response: Any) -> str | None:
    """Klucz zgłoszenia z odpowiedzi importu Xraya.

    Format odpowiedzi różni się między wersjami wtyczki, więc sprawdzamy
    kilka znanych kształtów zamiast zakładać jeden.
    """
    if not isinstance(response, dict):
        return None
    for key in ("testIssues", "issues", "tests"):
        items = response.get(key)
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return first.get("key") or first.get("issueKey")
    return response.get("key") or response.get("issueKey")


def build_exporter(provider: str, base_url: str, email: str, secret: str, config: dict[str, Any]):
    """Klient i eksporter właściwy dla dostawcy (Stories 8.8/8.9/8.11).

    Wszystkie trzy eksportery mają ten sam kontrakt ``export(rows, progress)``,
    więc wołający nie musi wiedzieć, do czego eksportuje. Fabryka stoi tutaj,
    a nie w zadaniu Celery, bo używa jej też synchronizacja (Story 8.11) —
    dwa miejsca budujące eksportery rozjechałyby się przy pierwszej zmianie.
    """
    from app.services.export.jira_tms_service import JiraTmsClient

    if provider == "xray":
        return XrayExporter(JiraTmsClient(base_url, email, secret), config)
    if provider == "zephyr":
        return ZephyrExporter(JiraTmsClient(base_url, email, secret), config)
    return TestRailExporter(TestRailClient(base_url, email, secret), config)


def build_tms_client(provider: str, base_url: str, email: str, secret: str):
    """Sam klient HTTP — synchronizacja czyta z TMS bez eksportera (Story 8.11)."""
    from app.services.export.jira_tms_service import JiraTmsClient

    if provider in ("xray", "zephyr"):
        return JiraTmsClient(base_url, email, secret)
    return TestRailClient(base_url, email, secret)
