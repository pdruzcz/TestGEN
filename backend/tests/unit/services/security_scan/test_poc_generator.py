"""Unit tests for the PoC generator — Story 4.10."""

import uuid

import pytest

from app.models.security_finding import AnalysisSource, ScanType, SecurityFinding, Severity
from app.services.security_scan.poc_generator import DISCLAIMER, PoCGenerator
from app.services.security_scan.poc_payloads.registry import PayloadRegistry


def _finding(
    vuln: str = "sql_injection",
    severity: Severity = Severity.HIGH,
    file_path: str | None = "app/db.py",
    code_snippet: str = 'cursor.execute("SELECT * FROM users WHERE id = " + uid)',
) -> SecurityFinding:
    f = SecurityFinding(
        project_id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        scan_type=ScanType.SAST,
        vulnerability_type=vuln,
        severity=severity,
        cwe_id="CWE-89",
        file_path=file_path,
        line_start=10,
        code_snippet=code_snippet,
        description="opis",
        confidence=0.8,
        source=AnalysisSource.NATIVE,
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


class TestNativePoC:
    @pytest.mark.asyncio
    async def test_sqli_native_poc(self):
        poc = await PoCGenerator().generate_poc(_finding())
        assert poc is not None
        assert poc.is_safe
        assert "OR 1=1" in poc.payload
        assert len(poc.reproduction_steps) >= 2
        assert poc.expected_effect
        assert poc.severity == "high"
        assert poc.engine_source == "native"
        assert poc.disclaimer == DISCLAIMER

    @pytest.mark.asyncio
    async def test_xss_native_poc(self):
        poc = await PoCGenerator().generate_poc(_finding(vuln="xss"))
        assert poc is not None
        assert "alert(1)" in poc.payload
        assert poc.is_safe

    @pytest.mark.asyncio
    async def test_command_injection_native_poc(self):
        poc = await PoCGenerator().generate_poc(_finding(vuln="command_injection"))
        assert poc is not None
        assert poc.is_safe

    @pytest.mark.asyncio
    async def test_unsupported_type_returns_none(self):
        poc = await PoCGenerator().generate_poc(_finding(vuln="weak_cryptography"))
        assert poc is None

    def test_destructive_payload_not_served(self):
        served = PayloadRegistry.get_payloads("sql_injection")
        assert all("DROP TABLE" not in t.payload for t in served)
        # The destructive example exists but only when explicitly including unsafe.
        all_payloads = PayloadRegistry.get_payloads("sql_injection", include_unsafe=True)
        assert any("DROP TABLE" in t.payload for t in all_payloads)


class TestLLMPoC:
    @pytest.mark.asyncio
    async def test_llm_payload_used_when_safe(self):
        gateway = _FakeGateway("```\n' OR 'a'='a\n```")
        poc = await PoCGenerator(llm_gateway=gateway).generate_poc(
            _finding(), engine_mode="llm", source_code="bad"
        )
        assert poc.engine_source == "llm"
        assert "OR 'a'='a" in poc.payload
        assert gateway.calls == 1

    @pytest.mark.asyncio
    async def test_llm_unsafe_payload_falls_back_to_native(self):
        gateway = _FakeGateway("1; DROP TABLE users--")
        poc = await PoCGenerator(llm_gateway=gateway).generate_poc(
            _finding(), engine_mode="llm", source_code="bad"
        )
        assert poc.engine_source == "native"
        assert poc.is_safe

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_native(self):
        gateway = _FakeGateway("", fail=True)
        poc = await PoCGenerator(llm_gateway=gateway).generate_poc(
            _finding(), engine_mode="llm", source_code="bad"
        )
        assert poc.engine_source == "native"

    @pytest.mark.asyncio
    async def test_llm_mode_without_gateway_uses_native(self):
        poc = await PoCGenerator().generate_poc(_finding(), engine_mode="llm")
        assert poc.engine_source == "native"
