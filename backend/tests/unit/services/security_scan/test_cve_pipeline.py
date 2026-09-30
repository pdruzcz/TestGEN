"""Unit tests for the CVE auto-update pipeline — Story 4.12.

Exercises the pure/offline-testable surface: deduplication/merge, upsert shaping
into ``cve_database``, affected-project matching, and LLM rule parsing/validation.
Network fetches are not touched here (covered by source-parsing tests).
"""

import re
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.security_finding import Severity
from app.services.security_scan.cve_pipeline import (
    CVEPipeline,
    CVERecord,
)


def _rec(cve_id, package, ecosystem="pypi", cvss=7.0, fixed=None, source="osv"):
    return CVERecord(
        cve_id=cve_id,
        package_name=package,
        ecosystem=ecosystem,
        cvss_score=cvss,
        description="d",
        severity=Severity.HIGH,
        fixed_version=fixed,
        source_db=source,
    )


class TestMergeAndDeduplicate:
    def test_dedup_by_cve_and_package(self):
        merged = CVEPipeline._merge_and_deduplicate(
            {
                "nvd": [_rec("CVE-2024-1", "requests", cvss=5.0)],
                "osv": [_rec("CVE-2024-1", "requests", cvss=8.0)],
            }
        )
        assert len(merged) == 1
        # Higher CVSS wins.
        assert merged[0].cvss_score == 8.0

    def test_same_cve_different_package_kept_separate(self):
        merged = CVEPipeline._merge_and_deduplicate(
            {"osv": [_rec("CVE-2024-2", "requests"), _rec("CVE-2024-2", "urllib3")]}
        )
        assert len(merged) == 2

    def test_fix_is_backfilled_from_other_source(self):
        merged = CVEPipeline._merge_and_deduplicate(
            {
                "nvd": [_rec("CVE-2024-3", "flask", cvss=9.0, fixed=None)],
                "osv": [_rec("CVE-2024-3", "flask", cvss=4.0, fixed="2.0.1")],
            }
        )
        assert len(merged) == 1
        assert merged[0].cvss_score == 9.0
        assert merged[0].fixed_version == "2.0.1"

    def test_non_cve_ids_dropped(self):
        merged = CVEPipeline._merge_and_deduplicate(
            {"osv": [_rec("NOTACVE", "x"), _rec("CVE-2024-4", "y")]}
        )
        assert [m.cve_id for m in merged] == ["CVE-2024-4"]


class TestSaveToDatabase:
    @pytest.mark.asyncio
    async def test_inserts_new_record(self):
        db = AsyncMock()
        db.add = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        pipeline = CVEPipeline()
        new, updated = await pipeline._save_to_database([_rec("CVE-2024-9", "requests")], db)

        assert new == 1
        assert updated == 0
        db.add.assert_called_once()
        db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_updates_existing_record(self):
        existing = SimpleNamespace(
            cvss_score=4.0, severity=Severity.MEDIUM, description="old",
            affected_versions=None, fixed_version=None, source_db="osv",
        )
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        db.execute.return_value = result

        pipeline = CVEPipeline()
        new, updated = await pipeline._save_to_database(
            [_rec("CVE-2024-9", "requests", cvss=9.1, fixed="3.0.0")], db
        )

        assert new == 0
        assert updated == 1
        assert existing.cvss_score == 9.1
        assert existing.fixed_version == "3.0.0"
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_record_without_package(self):
        db = AsyncMock()
        pipeline = CVEPipeline()
        new, updated = await pipeline._save_to_database([_rec("CVE-2024-9", "")], db)
        assert (new, updated) == (0, 0)
        db.add.assert_not_called()


class TestMatchAffected:
    def test_groups_findings_by_project_with_new_cves(self):
        pid = uuid.uuid4()
        findings = [
            SimpleNamespace(
                project_id=pid,
                finding_metadata={"package": "requests", "ecosystem": "pypi"},
            )
        ]
        records = [_rec("CVE-2024-1", "requests", "pypi")]

        affected = CVEPipeline._match_affected(findings, records)

        assert len(affected) == 1
        assert affected[0].project_id == pid
        assert affected[0].affected_packages == ["requests"]
        assert affected[0].new_cves == ["CVE-2024-1"]

    def test_finding_for_unrelated_package_is_ignored(self):
        findings = [
            SimpleNamespace(
                project_id=uuid.uuid4(),
                finding_metadata={"package": "numpy", "ecosystem": "pypi"},
            )
        ]
        records = [_rec("CVE-2024-1", "requests", "pypi")]
        assert CVEPipeline._match_affected(findings, records) == []

    def test_ecosystem_normalization_matches_pip_to_pypi(self):
        pid = uuid.uuid4()
        findings = [
            SimpleNamespace(
                project_id=pid,
                finding_metadata={"package": "requests", "ecosystem": "pip"},
            )
        ]
        records = [_rec("CVE-2024-1", "requests", "pypi")]
        affected = CVEPipeline._match_affected(findings, records)
        assert len(affected) == 1


class TestLastUpdateDate:
    @pytest.mark.asyncio
    async def test_defaults_to_lookback_when_no_log(self):
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        since = await CVEPipeline()._get_last_update_date(db)
        assert since < datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_uses_last_completed_date(self):
        ts = datetime(2026, 6, 1, tzinfo=UTC)
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = ts
        db.execute.return_value = result

        since = await CVEPipeline()._get_last_update_date(db)
        assert since == ts


class TestRuleGeneration:
    def test_parse_rule_response_builds_rule(self):
        rec = _rec("CVE-2024-7", "requests")
        text = "REGEX: eval\\(.*\\)\nTYPE: code_injection\nCWE: CWE-94"
        rule = CVEPipeline._parse_rule_response(text, rec)
        assert rule is not None
        assert rule.vulnerability_type == "code_injection"
        assert rule.cwe_id == "CWE-94"
        assert rule.patterns[0].regex.search("eval(x)")

    def test_parse_rule_response_rejects_invalid_regex(self):
        rec = _rec("CVE-2024-7", "requests")
        rule = CVEPipeline._parse_rule_response("REGEX: (unbalanced\nTYPE: x", rec)
        assert rule is None

    def test_parse_rule_response_requires_regex_line(self):
        rec = _rec("CVE-2024-7", "requests")
        assert CVEPipeline._parse_rule_response("TYPE: x\nCWE: CWE-1", rec) is None

    def test_validate_rule_passes_when_no_false_positives(self):
        from app.services.security_scan.rules.base import PY, RulePattern, VulnerabilityRule

        rule = VulnerabilityRule(
            id="r", name="r", vulnerability_type="t", cwe_id="CWE-1",
            owasp_category="A06", severity="high", description="d",
            patterns=(RulePattern(regex=re.compile("dangerous_call"), languages=PY),),
        )
        validation = CVEPipeline._validate_rule_on_golden_data(rule, ["safe = 1", "x = 2"])
        assert validation.passed
        assert validation.fpr == 0.0

    def test_validate_rule_fails_above_threshold(self):
        from app.services.security_scan.rules.base import PY, RulePattern, VulnerabilityRule

        rule = VulnerabilityRule(
            id="r", name="r", vulnerability_type="t", cwe_id="CWE-1",
            owasp_category="A06", severity="high", description="d",
            patterns=(RulePattern(regex=re.compile("x"), languages=PY),),
        )
        validation = CVEPipeline._validate_rule_on_golden_data(rule, ["x", "x", "x"])
        assert not validation.passed
        assert validation.fpr == 1.0


class TestUpdateOrchestration:
    @pytest.mark.asyncio
    async def test_update_records_source_failures_without_aborting(self):
        db = AsyncMock()
        # _get_last_update_date + _save_to_database + _find_affected_projects all use execute.
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        db.execute.return_value = result

        pipeline = CVEPipeline()

        async def boom(since):
            raise RuntimeError("network down")

        async def empty(since):
            return []

        pipeline._fetch_nvd_updates = boom
        pipeline._fetch_osv_updates = empty
        pipeline._fetch_github_advisories = empty

        res = await pipeline.update_cve_database(db)

        assert res.sources_status["nvd"].ok is False
        assert res.sources_status["osv"].ok is True
        assert any("network down" in e for e in res.errors)
        assert res.total_new == 0
