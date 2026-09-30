"""AzureDevOpsService — httpx client for Azure DevOps REST API v7.0.

Epic 5, Story 5.9.

Provides:
- test_connection(): verify PAT and organization
- create_work_item(): create a single work item (JSON Patch format)
- sync_from_gap_findings(): batch-create work items from gap findings
- sync_from_recommendations(): batch-create work items from recommendations

Authentication: Personal Access Token (PAT) via Basic auth.
The PAT is stored encrypted in IntegrationConfig as ``:{token}``.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.encryption import decrypt
from app.models.integration import IntegrationConfig

logger = logging.getLogger(__name__)

ADO_API_VERSION = "7.0"


@dataclass
class AdoWorkItemPayload:
    """Payload for creating an Azure DevOps work item (JSON Patch)."""

    title: str
    description: str
    work_item_type: str = "Task"
    tags: list[str] = field(default_factory=list)
    priority: int | None = None

    def to_patch_docs(self) -> list[dict[str, Any]]:
        """Convert to JSON Patch document list (Azure DevOps format)."""
        docs: list[dict[str, Any]] = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": self.title[:250],
            },
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": self.description,
            },
        ]
        if self.tags:
            docs.append({
                "op": "add",
                "path": "/fields/System.Tags",
                "value": "; ".join(self.tags),
            })
        if self.priority is not None:
            docs.append({
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.Priority",
                "value": self.priority,
            })
        return docs


@dataclass
class AdoWorkItemResult:
    """Result of creating a single work item."""

    id: int | None = None
    url: str | None = None
    error: str | None = None


@dataclass
class SyncResult:
    """Result of a batch sync operation."""

    total: int = 0
    synced: int = 0
    results: list[AdoWorkItemResult] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


class AzureDevOpsService:
    """Client for Azure DevOps REST API v7.0."""

    def __init__(self, config: IntegrationConfig):
        self.config = config
        self._base_url = config.base_url.rstrip("/")
        self._pat = decrypt(config.encrypted_credentials)

        settings = config.settings or {}
        self._organization = settings.get("organization", "")
        self._project = settings.get("project", "")
        self._default_work_item_type = settings.get("issue_type", "Task")

        token = base64.b64encode(f":{self._pat}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json-patch+json",
        }

    def test_connection(self) -> bool:
        """Verify that the PAT and organization are valid."""
        url = (
            f"https://dev.azure.com/{self._organization}/_apis/projects"
            f"?api-version={ADO_API_VERSION}"
        )
        try:
            resp = httpx.get(url, headers=self._headers, timeout=15)
            return resp.status_code == 200
        except httpx.HTTPError as e:
            logger.warning("Azure DevOps connection test failed: %s", e)
            return False

    def create_work_item(self, payload: AdoWorkItemPayload) -> AdoWorkItemResult:
        """Create a single work item in Azure DevOps."""
        if not self._organization or not self._project:
            return AdoWorkItemResult(error="Organization and project must be configured")

        wit_type = payload.work_item_type or self._default_work_item_type
        url = (
            f"https://dev.azure.com/{self._organization}/{self._project}"
            f"/_apis/wit/workitems/${wit_type}?api-version={ADO_API_VERSION}"
        )
        try:
            resp = httpx.post(
                url,
                headers=self._headers,
                json=payload.to_patch_docs(),
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                wid = data.get("id")
                return AdoWorkItemResult(
                    id=wid,
                    url=data.get("_links", {}).get("html", {}).get("href"),
                )
            else:
                return AdoWorkItemResult(error=self._extract_error(resp))
        except httpx.HTTPError as e:
            return AdoWorkItemResult(error=str(e))

    def sync_from_gap_findings(
        self,
        findings: list[Any],
    ) -> SyncResult:
        """Create work items from gap findings."""
        result = SyncResult(total=len(findings))
        for f in findings:
            gap_type = getattr(f, "gap_type", None)
            gap_str = gap_type.value if hasattr(gap_type, "value") else str(gap_type)
            severity = getattr(f, "severity", "warning")

            payload = AdoWorkItemPayload(
                title=f"[{gap_str.upper()}] {getattr(f, 'description', 'Gap finding')[:200]}",
                description=self._build_description(f),
                work_item_type=self._default_work_item_type,
                tags=["testgen-gap", gap_str],
                priority=self._map_priority(gap_str, severity),
            )
            item = self.create_work_item(payload)
            result.results.append(item)
            if item.id:
                result.synced += 1
            else:
                result.errors.append({
                    "finding": getattr(f, "id", "unknown"),
                    "error": item.error or "Unknown error",
                })
        return result

    def sync_from_recommendations(
        self,
        recommendations: list[Any],
    ) -> SyncResult:
        """Create work items from recommendations."""
        result = SyncResult(total=len(recommendations))
        for r in recommendations:
            priority_str = getattr(r, "priority", None)
            priority_val = priority_str.value if hasattr(priority_str, "value") else str(priority_str)

            payload = AdoWorkItemPayload(
                title=getattr(r, "title", "Recommendation")[:250],
                description=getattr(r, "description", ""),
                work_item_type=self._default_work_item_type,
                tags=["testgen-rec", priority_val],
                priority=self._map_rec_priority(priority_val),
            )
            item = self.create_work_item(payload)
            result.results.append(item)
            if item.id:
                result.synced += 1
            else:
                result.errors.append({
                    "recommendation": getattr(r, "id", "unknown"),
                    "error": item.error or "Unknown error",
                })
        return result

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _map_priority(self, gap_type: str, severity: str) -> int:
        """Map gap type + severity to Azure DevOps priority (1=highest, 4=lowest)."""
        if gap_type == "missing" and severity == "critical":
            return 1
        if gap_type == "inconsistent":
            return 1
        if severity == "critical":
            return 2
        if severity == "warning":
            return 3
        return 4

    def _map_rec_priority(self, priority: str) -> int:
        """Map recommendation priority to Azure DevOps priority."""
        mapping = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
        return mapping.get(priority, 3)

    def _build_description(self, finding: Any) -> str:
        """Build work item description from a gap finding."""
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
        if match_score is not None:
            parts.append(f"Score dopasowania: {match_score}")
        return "\n\n".join(parts) if parts else "Brak dodatkowych informacji."

    def _extract_error(self, resp: httpx.Response) -> str:
        """Extract error message from Azure DevOps response."""
        try:
            data = resp.json()
            msg = data.get("message", "")
            if msg:
                return msg
        except Exception:
            pass
        return f"HTTP {resp.status_code}: {resp.text[:200]}"
