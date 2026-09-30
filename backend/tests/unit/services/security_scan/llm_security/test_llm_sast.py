"""Unit tests for the LLM security analyzers — Story 4.13 (AC2).

Parsing is pure and tested directly; ``analyze`` is tested with a mocked LLM
gateway to confirm chunking, prompt dispatch and graceful failure handling.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.security_scan.llm_security import extract_json_array, normalize_severity
from app.services.security_scan.llm_security.llm_config import LLMConfigAnalyzer
from app.services.security_scan.llm_security.llm_sast import LLMSASTAnalyzer
from app.services.security_scan.llm_security.llm_taint import LLMTaintAnalyzer


class TestHelpers:
    def test_extract_plain_array(self):
        assert extract_json_array('[{"a": 1}]') == [{"a": 1}]

    def test_extract_fenced_json(self):
        content = '```json\n[{"vulnerability_type": "idor"}]\n```'
        assert extract_json_array(content) == [{"vulnerability_type": "idor"}]

    def test_extract_with_prose(self):
        content = 'Oto wyniki:\n[{"x": 2}]\nKoniec.'
        assert extract_json_array(content) == [{"x": 2}]

    def test_extract_invalid_returns_empty(self):
        assert extract_json_array("brak json") == []
        assert extract_json_array("[not valid]") == []

    def test_normalize_severity(self):
        assert normalize_severity("CRITICAL") == "critical"
        assert normalize_severity("bogus") == "medium"
        assert normalize_severity(None) == "medium"


class TestLLMSASTParse:
    def test_parses_findings(self):
        content = (
            '[{"vulnerability_type": "missing_authorization", "severity": "high", '
            '"line_start": 12, "description": "Brak kontroli dostępu", "cwe_id": "CWE-862", '
            '"recommendation": "Dodaj sprawdzenie roli"}]'
        )
        findings = LLMSASTAnalyzer.parse_response(content, "app/views.py")
        assert len(findings) == 1
        f = findings[0]
        assert f.vulnerability_type == "missing_authorization"
        assert f.severity == "high"
        assert f.line_start == 12
        assert f.file_path == "app/views.py"
        assert f.source == "llm"
        assert f.cwe_id == "CWE-862"
        assert f.recommendation == "Dodaj sprawdzenie roli"

    def test_skips_items_without_type(self):
        content = '[{"severity": "high"}, {"vulnerability_type": "xss"}]'
        findings = LLMSASTAnalyzer.parse_response(content, "a.py")
        assert len(findings) == 1
        assert findings[0].vulnerability_type == "xss"

    def test_empty_array(self):
        assert LLMSASTAnalyzer.parse_response("[]", "a.py") == []


class TestLLMTaintParse:
    def test_parses_with_source_sink_metadata(self):
        content = (
            '[{"vulnerability_type": "sql_injection", "severity": "critical", '
            '"line_start": 5, "description": "flow", "source": "request.args", '
            '"sink": "cursor.execute", "cwe_id": "CWE-89"}]'
        )
        findings = LLMTaintAnalyzer.parse_response(content, "db.py")
        assert len(findings) == 1
        f = findings[0]
        assert f.metadata["source"] == "request.args"
        assert f.metadata["sink"] == "cursor.execute"
        assert f.source == "llm"


class TestLLMConfigParse:
    def test_parses_holistic_finding(self):
        content = (
            '[{"vulnerability_type": "exposed_service", "severity": "high", '
            '"file": "docker-compose.yml", "description": "Port + brak TLS", '
            '"recommendation": "Włącz TLS"}]'
        )
        findings = LLMConfigAnalyzer.parse_response(content)
        assert len(findings) == 1
        assert findings[0].file_path == "docker-compose.yml"
        assert findings[0].source == "llm"

    def test_default_vuln_type(self):
        content = '[{"description": "problem", "severity": "low"}]'
        findings = LLMConfigAnalyzer.parse_response(content)
        assert findings[0].vulnerability_type == "insecure_configuration"


class TestLLMSASTAnalyze:
    async def test_no_gateway_returns_empty(self):
        analyzer = LLMSASTAnalyzer(llm_gateway=None)
        assert await analyzer.analyze([("a.py", "python", "code")]) == []

    async def test_dispatches_and_parses(self):
        gateway = AsyncMock()
        gateway.complete.return_value = SimpleNamespace(
            content='[{"vulnerability_type": "idor", "severity": "high", "line_start": 3, "description": "d"}]'
        )
        analyzer = LLMSASTAnalyzer(llm_gateway=gateway)
        findings = await analyzer.analyze([("a.py", "python", "code")])
        assert len(findings) == 1
        assert findings[0].vulnerability_type == "idor"
        gateway.complete.assert_awaited_once()

    async def test_failure_is_swallowed(self):
        gateway = AsyncMock()
        gateway.complete.side_effect = RuntimeError("llm down")
        analyzer = LLMSASTAnalyzer(llm_gateway=gateway)
        assert await analyzer.analyze([("a.py", "python", "code")]) == []


class TestLLMConfigAnalyze:
    async def test_empty_files_no_call(self):
        gateway = AsyncMock()
        analyzer = LLMConfigAnalyzer(llm_gateway=gateway)
        assert await analyzer.analyze([]) == []
        gateway.complete.assert_not_called()
