"""Unit tests for the patch generator — Story 4.11."""

import uuid

import pytest

from app.models.security_finding import AnalysisSource, ScanType, SecurityFinding, Severity
from app.services.security_scan.patch_generator import PatchGenerator
from app.services.security_scan.recommendation_engine import Recommendation

_ORIGINAL = 'def login(uid):\n    cursor.execute("SELECT * FROM users WHERE id = " + uid)\n    return cursor.fetchone()\n'
_FIXED = 'def login(uid):\n    cursor.execute("SELECT * FROM users WHERE id = %s", (uid,))\n    return cursor.fetchone()\n'


def _finding(
    vuln: str = "sql_injection",
    file_path: str | None = "app/db.py",
    line_start: int = 2,
    line_end: int | None = 2,
    code_snippet: str = _ORIGINAL,
) -> SecurityFinding:
    f = SecurityFinding(
        project_id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        scan_type=ScanType.SAST,
        vulnerability_type=vuln,
        severity=Severity.HIGH,
        cwe_id="CWE-89",
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        code_snippet=code_snippet,
        description="opis",
        confidence=0.8,
        source=AnalysisSource.NATIVE,
    )
    f.id = uuid.uuid4()
    return f


def _recommendation(fixed: str = _FIXED) -> Recommendation:
    return Recommendation(
        problem_description="p",
        risk_description="r",
        fix_description="f",
        fixed_code_snippet=fixed,
        diff="",
        language="python",
        engine_source="native",
    )


class TestSinglePatch:
    @pytest.mark.asyncio
    async def test_generates_unified_diff(self):
        finding = _finding()
        result = await PatchGenerator().generate_patch(finding, _recommendation(), _ORIGINAL)
        assert result.patch_content.startswith("--- a/app/db.py")
        assert "+++ b/app/db.py" in result.patch_content
        assert "@@" in result.patch_content
        assert "+    cursor.execute" in result.patch_content
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_hunk_header_reflects_line_start(self):
        finding = _finding(line_start=10, line_end=10)
        result = await PatchGenerator().generate_patch(finding, _recommendation(), _ORIGINAL)
        # line_start shifts the hunk header off line 1.
        assert "@@ -10" in result.patch_content or "@@ -11" in result.patch_content

    @pytest.mark.asyncio
    async def test_filename_includes_vuln_and_file(self):
        finding = _finding()
        result = await PatchGenerator().generate_patch(finding, _recommendation(), _ORIGINAL)
        assert result.patch_filename.startswith("fix_sql_injection_app_db_py_")
        assert result.patch_filename.endswith(".patch")

    @pytest.mark.asyncio
    async def test_identical_code_yields_empty_patch(self):
        finding = _finding()
        result = await PatchGenerator().generate_patch(finding, _recommendation(_ORIGINAL), _ORIGINAL)
        assert result.patch_content == ""
        assert result.is_valid is False


class TestValidation:
    def test_valid_patch_matches_source(self):
        gen = PatchGenerator()
        patch = gen._create_unified_diff(_ORIGINAL, _FIXED, "app/db.py", 1)
        validation = gen._validate_patch(patch, _ORIGINAL)
        assert validation.is_valid
        assert validation.can_apply

    def test_patch_not_matching_source_is_invalid(self):
        gen = PatchGenerator()
        patch = gen._create_unified_diff(_ORIGINAL, _FIXED, "app/db.py", 1)
        validation = gen._validate_patch(patch, "totally different source\n")
        assert validation.is_valid is False
        assert validation.error_message

    def test_empty_patch_is_invalid(self):
        validation = PatchGenerator()._validate_patch("", _ORIGINAL)
        assert validation.is_valid is False


class TestConflictDetection:
    def test_overlapping_ranges_are_critical(self):
        a = _finding(line_start=5, line_end=10)
        b = _finding(line_start=8, line_end=12)
        b.file_path = a.file_path
        conflicts = PatchGenerator()._detect_conflicts([a, b])
        assert len(conflicts) == 1
        assert conflicts[0].severity == "critical"
        assert 8 in conflicts[0].overlapping_lines

    def test_adjacent_ranges_are_warning(self):
        a = _finding(line_start=5, line_end=7)
        b = _finding(line_start=8, line_end=10)
        b.file_path = a.file_path
        conflicts = PatchGenerator()._detect_conflicts([a, b])
        assert len(conflicts) == 1
        assert conflicts[0].severity == "warning"

    def test_non_overlapping_ranges_no_conflict(self):
        a = _finding(line_start=5, line_end=7)
        b = _finding(line_start=20, line_end=22)
        b.file_path = a.file_path
        conflicts = PatchGenerator()._detect_conflicts([a, b])
        assert conflicts == []

    def test_different_files_no_conflict(self):
        a = _finding(line_start=5, line_end=10, file_path="a.py")
        b = _finding(line_start=5, line_end=10, file_path="b.py")
        conflicts = PatchGenerator()._detect_conflicts([a, b])
        assert conflicts == []


class TestBatch:
    @pytest.mark.asyncio
    async def test_batch_generates_patch_per_finding_with_conflicts(self):
        a = _finding(line_start=2, line_end=2)
        b = _finding(line_start=2, line_end=3)
        b.file_path = a.file_path
        b.code_snippet = _ORIGINAL
        results = await PatchGenerator().generate_batch_patches([a, b], db=None)
        assert len(results) == 2
        # Both share an overlapping range → each carries the conflict.
        assert all(r.conflicts for r in results)
        assert results[0].conflicts[0].severity == "critical"
