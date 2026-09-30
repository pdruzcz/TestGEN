"""Klienty Jiry — REST API v3 (Epic 5, Story 5.8) i v2 (Epic 8, Story 8.12).

Epic 5, Story 5.8.

Provides:
- test_connection(): verify credentials and base URL
- create_issue(): create a single Jira issue from a gap finding or recommendation
- sync_items(): batch-create issues from gap findings / recommendations

Authentication: email + API token (Atlassian basic auth).
Credentials are stored encrypted in IntegrationConfig and decrypted at runtime.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

from app.core.encryption import decrypt

if TYPE_CHECKING:
    from app.models.integration import IntegrationConfig

logger = logging.getLogger(__name__)

JIRA_API_V3 = "/rest/api/3"


@dataclass
class JiraIssuePayload:
    """Payload for creating a Jira issue."""

    project_key: str
    summary: str
    description: str
    issue_type: str = "Task"
    labels: list[str] = field(default_factory=list)
    priority: str | None = None

    def to_jira_dict(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": self.project_key},
            "summary": self.summary[:250],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": self.description[:3000]}],
                    }
                ],
            },
            "issuetype": {"name": self.issue_type},
        }
        if self.labels:
            fields["labels"] = self.labels
        if self.priority:
            fields["priority"] = {"name": self.priority}
        return {"fields": fields}


@dataclass
class JiraIssueResult:
    """Result of creating a single issue."""

    key: str | None = None
    url: str | None = None
    error: str | None = None


@dataclass
class SyncResult:
    """Result of a batch sync operation."""

    total: int = 0
    synced: int = 0
    results: list[JiraIssueResult] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


class JiraService:
    """Client for Jira REST API v3."""

    def __init__(self, config: IntegrationConfig):
        self.config = config
        self._base_url = config.base_url.rstrip("/")
        creds = decrypt(config.encrypted_credentials)
        parts = creds.split(":", 1)
        if len(parts) != 2:
            raise ValueError("Invalid credentials format (expected email:api_token)")
        self._email = parts[0]
        self._api_token = parts[1]
        self._project_key = (config.settings or {}).get("project_key", "") if config.settings else ""
        self._default_issue_type = (config.settings or {}).get("issue_type", "Task") if config.settings else "Task"

        token = base64.b64encode(f"{self._email}:{self._api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> bool:
        """Verify that the credentials and base URL are valid."""
        url = f"{self._base_url}{JIRA_API_V3}/myself"
        try:
            resp = httpx.get(url, headers=self._headers, timeout=15)
            return resp.status_code == 200
        except httpx.HTTPError as e:
            logger.warning("Jira connection test failed: %s", e)
            return False

    def get_project_key(self) -> str:
        return self._project_key

    def create_issue(self, payload: JiraIssuePayload) -> JiraIssueResult:
        """Create a single issue in Jira."""
        if not payload.project_key:
            payload.project_key = self._project_key
        if not payload.project_key:
            return JiraIssueResult(error="No project_key configured")

        url = f"{self._base_url}{JIRA_API_V3}/issue"
        try:
            resp = httpx.post(
                url,
                headers=self._headers,
                json=payload.to_jira_dict(),
                timeout=30,
            )
            if resp.status_code == 201:
                data = resp.json()
                key = data.get("key", "")
                return JiraIssueResult(
                    key=key,
                    url=f"{self._base_url}/browse/{key}",
                )
            else:
                err_msg = self._extract_error(resp)
                return JiraIssueResult(error=err_msg)
        except httpx.HTTPError as e:
            return JiraIssueResult(error=str(e))

    def sync_from_gap_findings(
        self,
        findings: list[Any],
    ) -> SyncResult:
        """Create Jira issues from gap findings (MISSING type)."""
        result = SyncResult(total=len(findings))
        for f in findings:
            gap_type = getattr(f, "gap_type", None)
            gap_str = gap_type.value if hasattr(gap_type, "value") else str(gap_type)
            severity = getattr(f, "severity", "warning")

            priority = self._map_priority(gap_str, severity)
            payload = JiraIssuePayload(
                project_key=self._project_key,
                summary=f"[{gap_str.upper()}] {getattr(f, 'description', 'Gap finding')[:200]}",
                description=self._build_description(f),
                issue_type=self._default_issue_type,
                labels=["testgen-gap", gap_str],
                priority=priority,
            )
            issue = self.create_issue(payload)
            result.results.append(issue)
            if issue.key:
                result.synced += 1
            else:
                result.errors.append(
                    {
                        "finding": getattr(f, "id", "unknown"),
                        "error": issue.error or "Unknown error",
                    }
                )
        return result

    def sync_from_recommendations(
        self,
        recommendations: list[Any],
    ) -> SyncResult:
        """Create Jira issues from recommendations."""
        result = SyncResult(total=len(recommendations))
        for r in recommendations:
            priority_str = getattr(r, "priority", None)
            priority_val = priority_str.value if hasattr(priority_str, "value") else str(priority_str)

            payload = JiraIssuePayload(
                project_key=self._project_key,
                summary=getattr(r, "title", "Recommendation")[:250],
                description=getattr(r, "description", ""),
                issue_type=self._default_issue_type,
                labels=["testgen-rec", priority_val],
                priority=self._map_rec_priority(priority_val),
            )
            issue = self.create_issue(payload)
            result.results.append(issue)
            if issue.key:
                result.synced += 1
            else:
                result.errors.append(
                    {
                        "recommendation": getattr(r, "id", "unknown"),
                        "error": issue.error or "Unknown error",
                    }
                )
        return result

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _map_priority(self, gap_type: str, severity: str) -> str | None:
        """Map gap type + severity to Jira priority."""
        if gap_type == "missing" and severity == "critical":
            return "Highest"
        if gap_type == "inconsistent":
            return "High"
        if severity == "critical":
            return "High"
        if severity == "warning":
            return "Medium"
        return "Low"

    def _map_rec_priority(self, priority: str) -> str | None:
        """Map recommendation priority to Jira priority."""
        mapping = {"P1": "Highest", "P2": "High", "P3": "Medium", "P4": "Low"}
        return mapping.get(priority, "Medium")

    def _build_description(self, finding: Any) -> str:
        """Build issue description from a gap finding."""
        parts = []
        req_text = getattr(finding, "requirement_text", None)
        if req_text:
            parts.append(f"Wymaganie: {req_text}")
        desc = getattr(finding, "description", None)
        if desc:
            parts.append(f"Opis luki: {desc}")
        code_ref = getattr(finding, "code_reference", None)
        if code_ref:
            parts.append(f"Referencja kodu: {code_ref}")
        match_score = getattr(finding, "match_score", None)
        if match_score:
            parts.append(f"Score dopasowania: {match_score}")
        return "\n\n".join(parts) if parts else "Brak dodatkowych informacji."

    def _extract_error(self, resp: httpx.Response) -> str:
        """Extract error message from Jira response."""
        try:
            data = resp.json()
            errors = data.get("errorMessages", [])
            if errors:
                return "; ".join(errors)
            errors_map = data.get("errors", {})
            if errors_map:
                return "; ".join(f"{k}: {v}" for k, v in errors_map.items())
        except Exception:
            pass
        return f"HTTP {resp.status_code}: {resp.text[:200]}"


# ── Import wymagań z Jiry — Epic 8, Story 8.12 ──────────────────────────────
#
# Osobny klient od ``JiraService`` powyżej z dwóch powodów. Po pierwsze jest
# asynchroniczny: import pobiera dziesiątki zgłoszeń i ich załączniki, a
# blokujące wywołania wstrzymywałyby pętlę zdarzeń zadania. Po drugie używa
# API **v2**, nie v3: v3 oddaje opis w formacie ADF (drzewo JSON), z którego
# nie da się wprost wyciąć sekcji „Acceptance Criteria" — v2 zwraca tekst
# w znacznikach wiki, czyli dokładnie to, co umiemy sparsować.

JIRA_API_V2 = "/rest/api/2"

# Jira nie odda więcej niż 100 zgłoszeń na stronę, niezależnie od tego,
# o ile poprosimy.
_MAX_PAGE = 100
_MAX_PAGES = 50
_TIMEOUT_SECONDS = 30


@dataclass
class JiraIssue:
    """Zgłoszenie Jiry sprowadzone do pól, których potrzebuje import."""

    key: str
    issue_type: str
    summary: str
    description: str
    priority: str | None
    labels: list[str]
    status: str
    updated: str | None
    epic_key: str | None
    parent_key: str | None
    attachments: list[dict[str, Any]]


class JiraImportError(Exception):
    """Błąd komunikacji z Jirą przy imporcie."""


class JiraImportClient:
    """Asynchroniczny klient odczytu Jiry na potrzeby importu (Story 8.12)."""

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.request(method, url, headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            raise JiraImportError(f"Jira nie odpowiada: {exc}") from exc

        if response.status_code == 401:
            raise JiraImportError("Jira odrzuciła poświadczenia")
        if response.status_code == 403:
            raise JiraImportError("Konto nie ma uprawnień do tego projektu Jiry")
        if response.status_code == 410:
            raise JiraImportError("Atlassian usunął ten endpoint — zaktualizuj TestGEN")
        if response.status_code >= 400:
            raise JiraImportError(f"Jira odpowiedziała kodem {response.status_code}")
        return response

    async def _get(self, path: str, **kwargs: Any) -> Any:
        return await self._request("GET", path, **kwargs)

    async def _post(self, path: str, **kwargs: Any) -> Any:
        return await self._request("POST", path, **kwargs)

    async def list_projects(self) -> list[dict[str, Any]]:
        """Projekty widoczne dla konta — do wyboru źródła importu (AC5)."""
        response = await self._get(f"{JIRA_API_V2}/project")
        payload = response.json()
        items = payload if isinstance(payload, list) else (payload.get("values") or [])
        return [
            {"key": str(item.get("key", "")), "name": str(item.get("name", ""))} for item in items if item.get("key")
        ]

    async def search_issues(self, jql: str) -> list[JiraIssue]:
        """Wszystkie zgłoszenia pasujące do JQL, z przejściem po stronach.

        Legacy ``GET /rest/api/2/search`` Atlassian usunął (HTTP 410,
        potwierdzone 2026-09-28 na Jira Cloud) — działa wyłącznie rozszerzony
        ``POST /rest/api/3/search/jql`` z paginacją po ``nextPageToken``.
        Opisy przychodzą w ADF; ``parse_issue`` sprowadza je na wiki.
        """
        issues: list[JiraIssue] = []
        next_token: str | None = None
        for _ in range(_MAX_PAGES):
            body: dict[str, Any] = {
                "jql": jql,
                "maxResults": _MAX_PAGE,
                "fields": [
                    "summary",
                    "description",
                    "issuetype",
                    "priority",
                    "labels",
                    "status",
                    "updated",
                    "parent",
                    "attachment",
                ],
            }
            if next_token:
                body["nextPageToken"] = next_token
            response = await self._post(f"{JIRA_API_V3}/search/jql", json=body)
            payload = response.json()
            issues.extend(parse_issue(raw) for raw in payload.get("issues") or [])
            next_token = payload.get("nextPageToken")
            if not next_token:
                break
        return issues

    async def get_issue(self, key: str) -> JiraIssue:
        response = await self._get(
            f"{JIRA_API_V2}/issue/{quote(key)}",
            params={"fields": "summary,description,issuetype,priority,labels,status,updated,parent,attachment"},
        )
        return parse_issue(response.json())

    async def get_attachment_content(self, attachment_id: str) -> bytes:
        """Treść załącznika. Adres ``content`` z listy pól bywa bezwzględny,
        więc korzystamy z endpointu po identyfikatorze — ten jest stabilny."""
        response = await self._get(
            f"{JIRA_API_V2}/attachment/content/{quote(str(attachment_id))}",
            follow_redirects=True,
        )
        return response.content


def _adf_text(content: Any) -> str:
    """Zbiera tekst z węzłów ADF (zagnieżdżone ``text`` wśród znaczników)."""
    parts: list[str] = []
    if isinstance(content, list):
        for child in content:
            if isinstance(child, dict):
                if "text" in child:
                    parts.append(str(child["text"]))
                parts.append(_adf_text(child.get("content")))
    return "".join(parts)


def adf_to_wiki(node: Any) -> str:
    """ADF (Atlassian Document Format) → znaczniki wiki Jiry.

    v3 zwraca opisy zgłoszeń w ADF (drzewo JSON), a parser kryteriów
    akceptacji czyta wiki — konwerter sprowadza drzewo do czterech
    konstrukcji, które ``parse_acceptance_criteria`` i ``wiki_to_markdown``
    rozumieją: nagłówków, akapitów oraz list punktowanych i numerowanych.
    Znaczniki formatowania (pogrubienia, linki) odpadają — dla importu
    liczy się treść, nie forma.
    """
    lines: list[str] = []

    def render(node: Any, prefix: str = "") -> None:
        if not isinstance(node, dict):
            return
        ntype = str(node.get("type", ""))
        if ntype == "heading":
            level = (node.get("attrs") or {}).get("level", 2)
            lines.append(f"h{level}. {_adf_text(node.get('content'))}")
            return
        if ntype in {"paragraph", "codeBlock"}:
            lines.append(f"{prefix}{_adf_text(node.get('content'))}".rstrip())
            return
        if ntype in {"bulletList", "numberedList"}:
            marker = "*" if ntype == "bulletList" else "#"
            for child in node.get("content") or []:
                render(child, prefix + marker)
            return
        if ntype == "listItem":
            for child in node.get("content") or []:
                if isinstance(child, dict) and child.get("type") in {"bulletList", "numberedList"}:
                    render(child, prefix)  # własny marker dopisze się wewnątrz
                else:
                    render(child, prefix + " ")
            return
        for child in node.get("content") or []:
            render(child, prefix)

    render(node)
    return "\n".join(line for line in lines if line.strip())


def parse_issue(raw: dict[str, Any]) -> JiraIssue:
    """Surowa odpowiedź Jiry → ``JiraIssue``.

    Pole ``parent`` niesie epik albo zadanie nadrzędne, zależnie od typu
    zgłoszenia; rozróżniamy je po typie rodzica, bo od tego zależy, czy
    powstanie moduł, czy podwymaganie (AC2). Opis z v3 przychodzi w ADF
    — sprowadzamy go na znaczniki wiki, żeby dalszy parser nie ruszał.
    """
    fields = raw.get("fields") or {}
    parent = fields.get("parent") or {}
    parent_type = ((parent.get("fields") or {}).get("issuetype") or {}).get("name", "")
    parent_key = str(parent.get("key")) if parent.get("key") else None
    is_epic_parent = str(parent_type).lower() == "epic"

    priority = fields.get("priority") or {}
    status = fields.get("status") or {}
    issue_type = (fields.get("issuetype") or {}).get("name", "")

    description = fields.get("description")
    if isinstance(description, dict):
        description = adf_to_wiki(description)

    return JiraIssue(
        key=str(raw.get("key", "")),
        issue_type=str(issue_type),
        summary=str(fields.get("summary") or ""),
        description=str(description or ""),
        priority=priority.get("name") if isinstance(priority, dict) else priority,
        labels=[str(label) for label in (fields.get("labels") or [])],
        status=str(status.get("name") or "") if isinstance(status, dict) else str(status or ""),
        updated=str(fields.get("updated")) if fields.get("updated") else None,
        epic_key=parent_key if is_epic_parent else None,
        parent_key=None if is_epic_parent else parent_key,
        attachments=[
            {
                "id": str(att.get("id", "")),
                "filename": str(att.get("filename", "")),
                "mime_type": att.get("mimeType"),
                "size": int(att.get("size") or 0),
            }
            for att in (fields.get("attachment") or [])
            if att.get("id") and att.get("filename")
        ],
    )
