"""Golden test for the patch generator — Story 4.11.

Uses a real vulnerable/fixed source pair to assert that the generated unified
diff is well-formed (git-apply shape), minimal and validates against the source.
"""

import uuid
from pathlib import Path

import pytest

from app.models.security_finding import AnalysisSource, ScanType, SecurityFinding, Severity
from app.services.security_scan.patch_generator import PatchGenerator
from app.services.security_scan.recommendation_engine import Recommendation

_DIR = Path(__file__).parent
_ORIGINAL = (_DIR / "sqli_login.py").read_text(encoding="utf-8")
_FIXED = (_DIR / "sqli_login_fixed.py").read_text(encoding="utf-8")


def _finding() -> SecurityFinding:
    f = SecurityFinding(
        project_id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        scan_type=ScanType.SAST,
        vulnerability_type="sql_injection",
        severity=Severity.HIGH,
        cwe_id="CWE-89",
        file_path="auth/login.py",
        line_start=5,
        line_end=6,
        code_snippet=_ORIGINAL,
        description="SQLi w authenticate()",
        confidence=0.9,
        source=AnalysisSource.NATIVE,
    )
    f.id = uuid.uuid4()
    return f


def _recommendation() -> Recommendation:
    return Recommendation(
        problem_description="p",
        risk_description="r",
        fix_description="f",
        fixed_code_snippet=_FIXED,
        diff="",
        language="python",
        engine_source="native",
    )


@pytest.mark.asyncio
async def test_golden_sqli_patch_is_well_formed():
    result = await PatchGenerator().generate_patch(_finding(), _recommendation(), _ORIGINAL)

    assert result.patch_content.startswith("--- a/auth/login.py")
    assert "+++ b/auth/login.py" in result.patch_content
    assert "@@" in result.patch_content
    # The vulnerable concatenation is removed, the parameterized query added.
    assert "-    query = \"SELECT * FROM users WHERE username = '\" + username + \"'\"" in result.patch_content
    assert '+    query = "SELECT * FROM users WHERE username = %s"' in result.patch_content
    assert result.is_valid


@pytest.mark.asyncio
async def test_golden_patch_is_minimal():
    result = await PatchGenerator().generate_patch(_finding(), _recommendation(), _ORIGINAL)
    added = [ln for ln in result.patch_content.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln for ln in result.patch_content.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    # Only the two vulnerable lines change; the function signature/return stay as context.
    assert len(added) == 2
    assert len(removed) == 2
