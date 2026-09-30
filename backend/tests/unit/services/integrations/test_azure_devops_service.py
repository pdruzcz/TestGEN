"""Unit tests for AzureDevOpsService — Epic 5, Story 5.9.

Tests work item payload construction (JSON Patch), priority mapping,
sync result aggregation. Uses mocked httpx calls.
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from app.services.integrations.azure_devops_service import (
    AdoWorkItemPayload,
    AdoWorkItemResult,
    AzureDevOpsService,
)


def _make_config(
    organization: str = "myorg",
    project: str = "MyProject",
    issue_type: str = "Task",
):
    from app.core.encryption import encrypt

    return SimpleNamespace(
        base_url="https://dev.azure.com/myorg",
        encrypted_credentials=encrypt("dummy-pat-token"),
        settings={
            "organization": organization,
            "project": project,
            "issue_type": issue_type,
        },
        provider="azure_devops",
    )


def _make_finding(
    fid: str = "gap-001",
    gap_type="missing",
    severity="critical",
    description="Brak implementacji validateInput",
    requirement_text="System powinien walidować dane",
    code_reference="src/api.py:15",
    match_score=0.38,
):
    gt = SimpleNamespace(value=gap_type) if isinstance(gap_type, str) else gap_type
    return SimpleNamespace(
        id=fid,
        gap_type=gt,
        severity=severity,
        description=description,
        requirement_text=requirement_text,
        code_reference=code_reference,
        match_score=match_score,
    )


def _make_recommendation(
    rid: str = "rec-001",
    title: str = "Dodaj logowanie błędów",
    description: str = "Brak logowania w module auth",
    priority="P2",
):
    pri = SimpleNamespace(value=priority) if isinstance(priority, str) else priority
    return SimpleNamespace(
        id=rid,
        title=title,
        description=description,
        priority=pri,
    )


# ── Work item payload (JSON Patch) ──────────────────────────────────────────


class TestAdoWorkItemPayload:
    def test_to_patch_docs_has_title_and_description(self):
        payload = AdoWorkItemPayload(
            title="Test item",
            description="Test description",
        )
        docs = payload.to_patch_docs()
        assert len(docs) == 2
        assert docs[0]["op"] == "add"
        assert docs[0]["path"] == "/fields/System.Title"
        assert docs[0]["value"] == "Test item"
        assert docs[1]["path"] == "/fields/System.Description"

    def test_tags_joined_with_semicolon(self):
        payload = AdoWorkItemPayload(
            title="T",
            description="D",
            tags=["tag1", "tag2"],
        )
        docs = payload.to_patch_docs()
        tag_doc = [d for d in docs if d["path"] == "/fields/System.Tags"]
        assert len(tag_doc) == 1
        assert tag_doc[0]["value"] == "tag1; tag2"

    def test_priority_added(self):
        payload = AdoWorkItemPayload(title="T", description="D", priority=2)
        docs = payload.to_patch_docs()
        pri_doc = [d for d in docs if d["path"] == "/fields/Microsoft.VSTS.Common.Priority"]
        assert len(pri_doc) == 1
        assert pri_doc[0]["value"] == 2

    def test_title_truncated(self):
        payload = AdoWorkItemPayload(title="x" * 300, description="D")
        docs = payload.to_patch_docs()
        title_doc = docs[0]
        assert len(title_doc["value"]) == 250


# ── Priority mapping ────────────────────────────────────────────────────────


class TestPriorityMapping:
    def test_missing_critical_is_1(self):
        svc = AzureDevOpsService(_make_config())
        assert svc._map_priority("missing", "critical") == 1

    def test_inconsistent_is_1(self):
        svc = AzureDevOpsService(_make_config())
        assert svc._map_priority("inconsistent", "warning") == 1

    def test_warning_is_3(self):
        svc = AzureDevOpsService(_make_config())
        assert svc._map_priority("different", "warning") == 3

    def test_info_is_4(self):
        svc = AzureDevOpsService(_make_config())
        assert svc._map_priority("extra", "info") == 4

    def test_rec_priority_p1(self):
        svc = AzureDevOpsService(_make_config())
        assert svc._map_rec_priority("P1") == 1

    def test_rec_priority_p4(self):
        svc = AzureDevOpsService(_make_config())
        assert svc._map_rec_priority("P4") == 4


# ── Create work item (mocked httpx) ─────────────────────────────────────────


class TestCreateWorkItem:
    @patch("app.services.integrations.azure_devops_service.httpx.post")
    def test_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 42,
            "_links": {"html": {"href": "https://dev.azure.com/myorg/MyProject/workitems/42"}},
        }
        mock_post.return_value = mock_resp

        svc = AzureDevOpsService(_make_config())
        payload = AdoWorkItemPayload(title="Test", description="desc")
        result = svc.create_work_item(payload)
        assert result.id == 42
        assert "workitems/42" in (result.url or "")
        assert result.error is None

    @patch("app.services.integrations.azure_devops_service.httpx.post")
    def test_error_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"message": "Invalid work item type"}
        mock_post.return_value = mock_resp

        svc = AzureDevOpsService(_make_config())
        result = svc.create_work_item(
            AdoWorkItemPayload(title="T", description="D")
        )
        assert result.id is None
        assert "Invalid work item type" in result.error

    def test_missing_org_and_project(self):
        config = _make_config(organization="", project="")
        svc = AzureDevOpsService(config)
        result = svc.create_work_item(AdoWorkItemPayload(title="T", description="D"))
        assert result.error is not None
        assert "Organization" in result.error


# ── Test connection ─────────────────────────────────────────────────────────


class TestConnection:
    @patch("app.services.integrations.azure_devops_service.httpx.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        svc = AzureDevOpsService(_make_config())
        assert svc.test_connection() is True

    @patch("app.services.integrations.azure_devops_service.httpx.get")
    def test_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        svc = AzureDevOpsService(_make_config())
        assert svc.test_connection() is False


# ── Sync from gap findings ──────────────────────────────────────────────────


class TestSyncFromGapFindings:
    @patch.object(AzureDevOpsService, "create_work_item")
    def test_all_success(self, mock_create):
        mock_create.side_effect = [
            AdoWorkItemResult(id=1, url="u1"),
            AdoWorkItemResult(id=2, url="u2"),
        ]
        svc = AzureDevOpsService(_make_config())
        findings = [_make_finding("g1"), _make_finding("g2")]
        result = svc.sync_from_gap_findings(findings)
        assert result.total == 2
        assert result.synced == 2
        assert len(result.errors) == 0

    @patch.object(AzureDevOpsService, "create_work_item")
    def test_partial_failure(self, mock_create):
        mock_create.side_effect = [
            AdoWorkItemResult(id=1),
            AdoWorkItemResult(error="Rate limited"),
        ]
        svc = AzureDevOpsService(_make_config())
        result = svc.sync_from_gap_findings([_make_finding("g1"), _make_finding("g2")])
        assert result.total == 2
        assert result.synced == 1
        assert len(result.errors) == 1

    def test_empty_findings(self):
        svc = AzureDevOpsService(_make_config())
        result = svc.sync_from_gap_findings([])
        assert result.total == 0
        assert result.synced == 0


# ── Sync from recommendations ───────────────────────────────────────────────


class TestSyncFromRecommendations:
    @patch.object(AzureDevOpsService, "create_work_item")
    def test_success(self, mock_create):
        mock_create.return_value = AdoWorkItemResult(id=1)
        svc = AzureDevOpsService(_make_config())
        result = svc.sync_from_recommendations([_make_recommendation()])
        assert result.total == 1
        assert result.synced == 1
