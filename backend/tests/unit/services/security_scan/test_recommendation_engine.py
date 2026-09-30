"""Unit tests for the recommendation engine — Story 4.9."""

import uuid

import pytest

from app.models.security_finding import AnalysisSource, ScanType, SecurityFinding, Severity
from app.services.security_scan.recommendation_engine import RecommendationEngine


def _finding(
    vuln: str = "sql_injection",
    cwe: str | None = "CWE-89",
    file_path: str | None = "app/db.py",
    code_snippet: str = 'cursor.execute("SELECT * FROM users WHERE id = " + user_id)',
    metadata: dict | None = None,
) -> SecurityFinding:
    f = SecurityFinding(
        project_id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        scan_type=ScanType.SAST,
        vulnerability_type=vuln,
        severity=Severity.HIGH,
        cwe_id=cwe,
        file_path=file_path,
        line_start=10,
        code_snippet=code_snippet,
        description="opis",
        confidence=0.8,
        source=AnalysisSource.NATIVE,
        finding_metadata=metadata,
    )
    f.id = uuid.uuid4()
    return f


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeGateway:
    def __init__(self, content: str, fail: bool = False) -> None:
        self._content = content
        self._fail = fail
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1
        if self._fail:
            raise RuntimeError("LLM down")
        return _FakeResponse(self._content)


class TestNativeRecommendation:
    @pytest.mark.asyncio
    async def test_sqli_python_native(self):
        rec = await RecommendationEngine().generate_recommendation(_finding())
        assert rec.engine_source == "native"
        assert rec.language == "python"
        assert "%s" in rec.fixed_code_snippet
        assert "SQL Injection" in rec.problem_description or "SQL" in rec.problem_description
        assert rec.diff  # diff against the vulnerable snippet

    @pytest.mark.asyncio
    async def test_language_inferred_from_extension(self):
        f = _finding(file_path="src/Repo.java", code_snippet="stmt.execute(sql + id)")
        rec = await RecommendationEngine().generate_recommendation(f)
        assert rec.language == "java"
        assert "PreparedStatement" in rec.fixed_code_snippet

    @pytest.mark.asyncio
    async def test_framework_from_metadata_selects_orm_template(self):
        f = _finding(metadata={"framework": "sqlalchemy"})
        rec = await RecommendationEngine().generate_recommendation(f)
        assert "session.query" in rec.fixed_code_snippet

    @pytest.mark.asyncio
    async def test_unknown_vuln_falls_back_to_generic(self):
        f = _finding(vuln="totally_unknown", cwe=None)
        rec = await RecommendationEngine().generate_recommendation(f)
        assert rec.engine_source == "native"
        assert rec.problem_description

    @pytest.mark.asyncio
    async def test_xss_native(self):
        f = _finding(
            vuln="xss",
            cwe="CWE-79",
            file_path="app/views.py",
            code_snippet="return '<p>' + user_input + '</p>'",
        )
        rec = await RecommendationEngine().generate_recommendation(f)
        assert rec.language == "python"
        assert "escape" in rec.fixed_code_snippet.lower()


class TestLLMRecommendation:
    @pytest.mark.asyncio
    async def test_llm_path_uses_returned_code(self):
        gateway = _FakeGateway("```python\ncursor.execute('SELECT 1 WHERE id=%s', (uid,))\n```")
        rec = await RecommendationEngine(llm_gateway=gateway).generate_recommendation(
            _finding(), source_code="bad", engine_mode="llm"
        )
        assert rec.engine_source == "llm"
        assert "cursor.execute" in rec.fixed_code_snippet
        assert gateway.calls == 1

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_native(self):
        gateway = _FakeGateway("", fail=True)
        rec = await RecommendationEngine(llm_gateway=gateway).generate_recommendation(
            _finding(), source_code="bad", engine_mode="llm"
        )
        assert rec.engine_source == "native"

    @pytest.mark.asyncio
    async def test_llm_mode_without_gateway_uses_native(self):
        rec = await RecommendationEngine().generate_recommendation(
            _finding(), engine_mode="llm"
        )
        assert rec.engine_source == "native"
