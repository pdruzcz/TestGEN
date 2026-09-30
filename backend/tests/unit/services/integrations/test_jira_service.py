"""Unit tests for JiraService — Epic 5, Story 5.8.

Tests Jira issue payload construction, priority mapping, description building,
and sync result aggregation. Uses mocked httpx calls.
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from app.services.integrations.jira_service import (
    JiraIssuePayload,
    JiraService,
    JiraIssueResult,
    SyncResult,
)


def _make_config(
    base_url: str = "https://test.atlassian.net",
    project_key: str = "TST",
    issue_type: str = "Task",
):
    from app.core.encryption import encrypt

    creds = encrypt("user@example.com:api-token-123")
    return SimpleNamespace(
        base_url=base_url,
        encrypted_credentials=creds,
        settings={"project_key": project_key, "issue_type": issue_type},
        provider="jira",
    )


def _make_finding(
    fid: str = "gap-001",
    gap_type="missing",
    severity="critical",
    description="Brak implementacji calculateTax",
    requirement_text="System powinien obliczać podatek",
    code_reference="src/tax.py:42",
    match_score=0.45,
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
    title: str = "Dodaj walidację danych wejściowych",
    description: str = "Brak walidacji w endpointzie /api/users",
    priority="P1",
):
    pri = SimpleNamespace(value=priority) if isinstance(priority, str) else priority
    return SimpleNamespace(
        id=rid,
        title=title,
        description=description,
        priority=pri,
    )


# ── JiraIssuePayload ─────────────────────────────────────────────────────────


class TestJiraIssuePayload:
    def test_to_jira_dict_has_required_fields(self):
        payload = JiraIssuePayload(
            project_key="TST",
            summary="Test issue",
            description="Test description",
        )
        d = payload.to_jira_dict()
        assert d["fields"]["project"]["key"] == "TST"
        assert d["fields"]["summary"] == "Test issue"
        assert d["fields"]["issuetype"]["name"] == "Task"

    def test_summary_truncated(self):
        payload = JiraIssuePayload(
            project_key="TST",
            summary="x" * 300,
            description="d",
        )
        assert len(payload.to_jira_dict()["fields"]["summary"]) == 250

    def test_labels_and_priority(self):
        payload = JiraIssuePayload(
            project_key="TST",
            summary="Test",
            description="d",
            labels=["bug", "testgen"],
            priority="High",
        )
        d = payload.to_jira_dict()
        assert d["fields"]["labels"] == ["bug", "testgen"]
        assert d["fields"]["priority"]["name"] == "High"


# ── Priority mapping ─────────────────────────────────────────────────────────


class TestPriorityMapping:
    def test_missing_critical_is_highest(self):
        svc = JiraService(_make_config())
        assert svc._map_priority("missing", "critical") == "Highest"

    def test_inconsistent_is_high(self):
        svc = JiraService(_make_config())
        assert svc._map_priority("inconsistent", "warning") == "High"

    def test_warning_is_medium(self):
        svc = JiraService(_make_config())
        assert svc._map_priority("different", "warning") == "Medium"

    def test_info_is_low(self):
        svc = JiraService(_make_config())
        assert svc._map_priority("extra", "info") == "Low"

    def test_rec_priority_p1(self):
        svc = JiraService(_make_config())
        assert svc._map_rec_priority("P1") == "Highest"

    def test_rec_priority_p4(self):
        svc = JiraService(_make_config())
        assert svc._map_rec_priority("P4") == "Low"


# ── Description building ─────────────────────────────────────────────────────


class TestDescriptionBuilding:
    def test_builds_from_finding(self):
        svc = JiraService(_make_config())
        f = _make_finding()
        desc = svc._build_description(f)
        assert "calculateTax" in desc
        assert "Wymaganie:" in desc
        assert "Score dopasowania:" in desc

    def test_empty_finding(self):
        svc = JiraService(_make_config())
        f = SimpleNamespace(
            requirement_text=None,
            description=None,
            code_reference=None,
            match_score=None,
        )
        desc = svc._build_description(f)
        assert "Brak dodatkowych informacji" in desc


# ── Create issue (mocked httpx) ──────────────────────────────────────────────


class TestCreateIssue:
    @patch("app.services.integrations.jira_service.httpx.post")
    def test_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"key": "TST-101"}
        mock_post.return_value = mock_resp

        svc = JiraService(_make_config())
        payload = JiraIssuePayload(
            project_key="TST",
            summary="Test issue",
            description="desc",
        )
        result = svc.create_issue(payload)
        assert result.key == "TST-101"
        assert result.url == "https://test.atlassian.net/browse/TST-101"
        assert result.error is None

    @patch("app.services.integrations.jira_service.httpx.post")
    def test_error_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"errorMessages": ["Invalid project key"]}
        mock_post.return_value = mock_resp

        svc = JiraService(_make_config())
        result = svc.create_issue(
            JiraIssuePayload(project_key="BAD", summary="s", description="d")
        )
        assert result.key is None
        assert "Invalid project key" in result.error


# ── Test connection (mocked httpx) ───────────────────────────────────────────


class TestConnection:
    @patch("app.services.integrations.jira_service.httpx.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        svc = JiraService(_make_config())
        assert svc.test_connection() is True

    @patch("app.services.integrations.jira_service.httpx.get")
    def test_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        svc = JiraService(_make_config())
        assert svc.test_connection() is False


# ── Sync from gap findings ──────────────────────────────────────────────────


class TestSyncFromGapFindings:
    @patch.object(JiraService, "create_issue")
    def test_all_success(self, mock_create):
        mock_create.side_effect = [
            JiraIssueResult(key="TST-1", url="u1"),
            JiraIssueResult(key="TST-2", url="u2"),
        ]
        svc = JiraService(_make_config())
        findings = [_make_finding("g1"), _make_finding("g2")]
        result = svc.sync_from_gap_findings(findings)
        assert result.total == 2
        assert result.synced == 2
        assert len(result.errors) == 0

    @patch.object(JiraService, "create_issue")
    def test_partial_failure(self, mock_create):
        mock_create.side_effect = [
            JiraIssueResult(key="TST-1"),
            JiraIssueResult(error="Rate limited"),
        ]
        svc = JiraService(_make_config())
        findings = [_make_finding("g1"), _make_finding("g2")]
        result = svc.sync_from_gap_findings(findings)
        assert result.total == 2
        assert result.synced == 1
        assert len(result.errors) == 1
        assert result.errors[0]["finding"] == "g2"

    def test_empty_findings(self):
        svc = JiraService(_make_config())
        result = svc.sync_from_gap_findings([])
        assert result.total == 0
        assert result.synced == 0


# ── Sync from recommendations ────────────────────────────────────────────────


class TestSyncFromRecommendations:
    @patch.object(JiraService, "create_issue")
    def test_success(self, mock_create):
        mock_create.return_value = JiraIssueResult(key="TST-1")
        svc = JiraService(_make_config())
        recs = [_make_recommendation()]
        result = svc.sync_from_recommendations(recs)
        assert result.total == 1
        assert result.synced == 1
