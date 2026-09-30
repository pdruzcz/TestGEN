"""Import wymagań z Jiry — Epic 8, Story 8.12.

Zgłoszenie Jiry i wymaganie TestGEN to dwa różne byty; ten moduł zajmuje się
przełożeniem jednego na drugie oraz przebiegiem całego importu.

Trzy decyzje kształtują ten kod:

* **Zaimportowane wymagania wiszą przy syntetycznym dokumencie.** Wymagania
  w TestGEN należą do pliku źródłowego (Epic 2), a Jira nie ma pliku. Import
  zakłada więc jeden „dokument" na projekt Jiry i to pod nim gromadzi
  wymagania — dzięki temu ekrany wymagań, gap analysis i macierz śledzenia
  działają bez żadnej wiedzy o Jirze.

* **Import przyrostowy opiera się na `last_import_at`, nie na liczniku.**
  Znacznik przesuwa wyłącznie udany przebieg; nieudany zostawia go tam, gdzie
  był, więc zgłoszenia z przerwanego importu wrócą przy następnym.

* **Błąd jednego zgłoszenia nie przerywa importu.** Przy stu historyjkach
  jedna z uszkodzonym opisem nie może unieważnić pozostałych — trafia do
  listy pominiętych.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.integrations.jira_service import JiraIssue

logger = logging.getLogger(__name__)

# Nagłówek sekcji z kryteriami akceptacji w znacznikach wiki Jiry:
# ``h2. Acceptance Criteria``, ``h3. Kryteria akceptacji`` itp.
_AC_HEADING = re.compile(
    r"^h[1-6]\.\s*(?:acceptance\s+criteria|kryteria\s+akceptacji|ac)\s*:?\s*$",
    re.IGNORECASE,
)
_ANY_HEADING = re.compile(r"^h[1-6]\.\s", re.IGNORECASE)
# Punkt listy: ``* tekst``, ``- tekst``, ``# tekst`` (lista numerowana w wiki).
_BULLET = re.compile(r"^\s*(?:[*\-#]+)\s+(.*\S)\s*$")

# Typ zgłoszenia → typ wymagania (AC2). Bug opisuje zachowanie, którego
# system wykazywać **nie** powinien, stąd „negative".
ISSUE_TYPE_TO_REQUIREMENT: dict[str, str] = {
    "story": "functional",
    "epic": "functional",
    "bug": "negative",
    "sub-task": "functional",
    "subtask": "functional",
}

# Priorytet Jiry → priorytet wymagania.
PRIORITY_MAP: dict[str, str] = {
    "highest": "critical",
    "blocker": "critical",
    "critical": "critical",
    "high": "high",
    "major": "high",
    "medium": "medium",
    "normal": "medium",
    "low": "low",
    "lowest": "low",
    "minor": "low",
    "trivial": "low",
}
DEFAULT_PRIORITY = "medium"


@dataclass
class ImportOutcome:
    """Podsumowanie jednego przebiegu importu."""

    requirements: list[dict[str, Any]] = field(default_factory=list)
    attachments: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "imported": len(self.requirements),
            "attachments": self.attachments,
            "skipped": self.skipped,
            "errors": self.errors,
        }


# ── budowa zapytania ────────────────────────────────────────────────────────


def build_jql(
    project_key: str,
    issue_types: list[str],
    updated_after: datetime | None = None,
) -> str:
    """Zapytanie JQL dla importu (AC1, AC4).

    Data jest formatowana bez strefy i sekund, bo JQL nie przyjmuje ISO 8601
    ze strefą — Jira interpretuje ją w strefie instancji.
    """
    if not project_key:
        raise ValueError("Brak klucza projektu Jiry")

    safe_key = project_key.replace('"', "")
    clauses = [f'project = "{safe_key}"']

    types = [t for t in issue_types if t]
    if types:
        joined = ", ".join(f'"{t}"' for t in types)
        clauses.append(f"issuetype in ({joined})")

    if updated_after is not None:
        moment = updated_after.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
        clauses.append(f'updated >= "{moment}"')

    return " AND ".join(clauses) + " ORDER BY updated ASC"


# ── konwersja opisu ─────────────────────────────────────────────────────────


def parse_acceptance_criteria(description: str) -> list[str]:
    """Kryteria akceptacji z opisu w znacznikach wiki (AC1).

    Szukamy nagłówka „Acceptance Criteria" (albo polskiego odpowiednika)
    i zbieramy punkty listy aż do następnego nagłówka. Zdanie bez punktora
    kończy sekcję: w praktyce jest to akapit komentarza, nie kryterium.
    """
    if not description:
        return []

    criteria: list[str] = []
    inside = False
    for line in description.splitlines():
        stripped = line.strip()
        if _AC_HEADING.match(stripped):
            inside = True
            continue
        if not inside:
            continue
        if _ANY_HEADING.match(stripped):
            break
        if not stripped:
            continue
        match = _BULLET.match(stripped)
        if match:
            criteria.append(_strip_wiki(match.group(1)))
            continue
        if criteria:
            break
    return [c for c in criteria if c]


def wiki_to_markdown(text: str) -> str:
    """Znaczniki wiki Jiry → Markdown, w zakresie, który realnie występuje.

    Pełnej konwersji nie robimy: opis trafia do wymagania jako tekst dla
    człowieka i dla analizy luk, więc liczy się czytelność, a nie wierność
    każdemu znacznikowi Jiry.
    """
    if not text:
        return ""

    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        heading = re.match(r"^h([1-6])\.\s*(.*)$", line, re.IGNORECASE)
        if heading:
            level = int(heading.group(1))
            lines.append(f"{'#' * level} {heading.group(2)}")
            continue
        bullet = re.match(r"^(\s*)([*\-]+)\s+(.*)$", line)
        if bullet:
            depth = len(bullet.group(2)) - 1
            lines.append(f"{'  ' * depth}- {_strip_wiki(bullet.group(3))}")
            continue
        numbered = re.match(r"^(\s*)#+\s+(.*)$", line)
        if numbered:
            lines.append(f"1. {_strip_wiki(numbered.group(2))}")
            continue
        lines.append(_strip_wiki(line))
    return "\n".join(lines).strip()


def _strip_wiki(text: str) -> str:
    """Zamienia znaczniki inline: pogrubienie, kursywę, kod i odnośniki."""
    result = re.sub(r"\{\{(.+?)\}\}", r"`\1`", text)
    result = re.sub(r"(?<!\w)\*(\S(?:.*?\S)?)\*(?!\w)", r"**\1**", result)
    result = re.sub(r"(?<!\w)_(\S(?:.*?\S)?)_(?!\w)", r"*\1*", result)
    # Odnośnik wiki: [etykieta|adres] albo [adres].
    result = re.sub(r"\[([^\]|]+)\|([^\]]+)\]", r"[\1](\2)", result)
    return result.strip()


# ── konwersja zgłoszenia ────────────────────────────────────────────────────


def requirement_type_for(issue_type: str) -> str:
    return ISSUE_TYPE_TO_REQUIREMENT.get(str(issue_type).strip().lower(), "functional")


def priority_for(jira_priority: str | None) -> str:
    return PRIORITY_MAP.get(str(jira_priority or "").strip().lower(), DEFAULT_PRIORITY)


def module_for(issue: JiraIssue) -> str:
    """Moduł wymagania. Epik grupuje historyjki, więc to on jest modułem (AC2).

    Epik sam w sobie też jest modułem — swoim własnym — bo inaczej wymagania
    z epiku i epik-rodzic wylądowałyby w dwóch różnych grupach.
    """
    if str(issue.issue_type).strip().lower() == "epic":
        return issue.key
    return issue.epic_key or issue.parent_key or "(bez epiku)"


def convert_issue(issue: JiraIssue) -> dict[str, Any]:
    """Zgłoszenie Jiry → wymaganie w formacie trzymanym w ``result_data``.

    Kształt jest ten sam, co u wymagań wydobytych z dokumentów (Epic 2), więc
    ekrany wymagań i analiza luk nie muszą wiedzieć, skąd wymaganie pochodzi.
    """
    if not issue.key:
        raise ValueError("Zgłoszenie bez klucza")

    body = wiki_to_markdown(issue.description)
    criteria = parse_acceptance_criteria(issue.description)

    return {
        "req_id": issue.key,
        "text": issue.summary or issue.key,
        "type": requirement_type_for(issue.issue_type),
        "priority": priority_for(issue.priority),
        "source_section_id": module_for(issue),
        "source_section_title": issue.epic_key or issue.parent_key or issue.key,
        "confidence": 1.0,
        # Wymaganie nie zostało wywnioskowane z tekstu, tylko przepisane
        # z systemu, w którym ktoś je świadomie zapisał — stąd pewność 1.0
        # i własna metoda, odróżnialna od ekstrakcji natywnej i z LLM-a.
        "extraction_method": "jira_import",
        "source": "jira",
        "reasoning": None,
        "status": "extracted",
        "jira_key": issue.key,
        "jira_issue_type": issue.issue_type,
        "jira_status": issue.status,
        "jira_updated": issue.updated,
        "body": body,
        "criteria": criteria,
        "tags": list(issue.labels),
        "parent_key": issue.parent_key,
        "epic_key": issue.epic_key,
    }


def merge_requirements(
    existing: list[dict[str, Any]], imported: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Scala nowo pobrane wymagania z już zapisanymi (AC4).

    Dopasowanie po ``jira_key``: zgłoszenie zmienione w Jirze nadpisuje swoją
    poprzednią wersję zamiast tworzyć drugie wymaganie. Zachowujemy przy tym
    decyzję z przeglądu (``status``) — import nie może cofać akceptacji
    wymagania, którą ktoś świadomie podjął.
    """
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for item in existing:
        key = str(item.get("jira_key") or item.get("req_id") or "")
        if not key:
            continue
        by_key[key] = dict(item)
        order.append(key)

    for item in imported:
        key = str(item.get("jira_key") or item.get("req_id") or "")
        if not key:
            continue
        previous = by_key.get(key)
        merged = dict(item)
        if previous is not None:
            merged["status"] = previous.get("status", merged.get("status", "extracted"))
        else:
            order.append(key)
        by_key[key] = merged

    return [by_key[key] for key in order]


def attachments_of(issues: list[JiraIssue]) -> list[tuple[str, dict[str, Any]]]:
    """Załączniki wszystkich zgłoszeń, z kluczem zgłoszenia przy każdym."""
    return [(issue.key, att) for issue in issues for att in issue.attachments]


def convert_all(issues: list[JiraIssue]) -> ImportOutcome:
    """Konwertuje zgłoszenia, pomijając te, których nie da się przełożyć."""
    outcome = ImportOutcome()
    for issue in issues:
        try:
            outcome.requirements.append(convert_issue(issue))
        except Exception as exc:
            outcome.skipped += 1
            outcome.errors.append(f"{issue.key or '(bez klucza)'}: {exc}")
            logger.warning("Pomijam zgłoszenie %s: %s", issue.key, exc)
    return outcome


# ── syntetyczny dokument ────────────────────────────────────────────────────


def render_document(project_key: str, requirements: list[dict[str, Any]]) -> str:
    """Markdown z zaimportowanych wymagań — treść syntetycznego dokumentu.

    Dokument istnieje z dwóch powodów: wymagania w TestGEN wiszą przy pliku
    źródłowym, a użytkownik musi mieć co otworzyć, gdy zechce zobaczyć, co
    właściwie zostało zaimportowane.
    """
    lines = [f"# Wymagania zaimportowane z Jiry ({project_key})", ""]
    for item in requirements:
        lines.append(f"## {item.get('jira_key', '')} — {item.get('text', '')}")
        lines.append("")
        body = str(item.get("body") or "").strip()
        if body:
            lines.extend([body, ""])
        criteria = item.get("criteria") or []
        if criteria:
            lines.append("### Kryteria akceptacji")
            lines.extend(f"- {c}" for c in criteria)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def sections_payload(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    """``result_data`` udającego przetworzenie dokumentu.

    Bez niego endpointy wymagań (Epic 2) odpowiadałyby 202 „analiza
    nieukończona" — sprawdzają obecność wyniku ``document_preprocessing``,
    który przy imporcie nie miałby skąd powstać.
    """
    sections = [
        {
            "section_id": str(item.get("jira_key") or f"REQ-{index}"),
            "title": str(item.get("text") or ""),
            "level": 1,
            "content": str(item.get("body") or "")[:1000],
            "page_number": None,
            "position": index,
            "section_type": "requirements",
            "parent_section_id": None,
            "children_count": 0,
        }
        for index, item in enumerate(requirements)
    ]
    return {
        "document_structure": {
            "filename": "",
            "format": "md",
            "sections_count": len(sections),
            "tables_count": 0,
            "processing_time_ms": 0,
            "artifact_count": 0,
            "polish_char_issues_fixed": 0,
            "compression_ratio": 1.0,
        },
        "sections": sections,
        "tables": [],
    }


def requirements_payload(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    """``result_data`` wyniku ``requirements`` — kształt jak u Epiku 2."""
    return {"requirements": requirements, "imported_at": datetime.now(UTC).isoformat()}
