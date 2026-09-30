"""Unit tests for the SAST engine — Epic 4, Story 4.1.

Exercise the pure, DB-free surface of :class:`SASTEngine`: native pattern
matching, confidence scoring, severity mapping and native/LLM merge.
"""

from app.services.security_scan.rules import RawFinding
from app.services.security_scan.sast_engine import SASTEngine


class TestNativePatternMatching:
    def test_detects_python_eval(self):
        engine = SASTEngine()
        code = "result = eval(user_input)\n"
        findings = engine.scan_code(code, "python", "app.py")
        assert any(f.vulnerability_type == "code_injection" for f in findings)

    def test_detects_command_injection(self):
        engine = SASTEngine()
        code = "os.system('rm -rf ' + path)\n"
        findings = engine.scan_code(code, "python", "app.py")
        assert any(f.vulnerability_type == "command_injection" for f in findings)
        cmd = next(f for f in findings if f.vulnerability_type == "command_injection")
        assert cmd.severity == "critical"

    def test_detects_sql_injection_fstring(self):
        engine = SASTEngine()
        code = 'query = f"SELECT * FROM users WHERE id = {uid}"\n'
        findings = engine.scan_code(code, "python", "db.py")
        assert any(f.vulnerability_type == "sql_injection" for f in findings)

    def test_detects_hardcoded_secret(self):
        engine = SASTEngine()
        code = 'api_key = "sk_live_abcdef123456"\n'
        findings = engine.scan_code(code, "python", "config.py")
        assert any(f.vulnerability_type == "hardcoded_secret" for f in findings)

    def test_detects_js_innerhtml_xss(self):
        engine = SASTEngine()
        code = "el.innerHTML = userData;\n"
        findings = engine.scan_code(code, "javascript", "ui.js")
        assert any(f.vulnerability_type == "xss" for f in findings)

    def test_clean_code_yields_no_findings(self):
        engine = SASTEngine()
        code = "def add(a, b):\n    return a + b\n"
        assert engine.scan_code(code, "python", "math.py") == []

    def test_comment_lines_are_skipped(self):
        engine = SASTEngine()
        code = "# eval(user_input) is dangerous\n"
        assert engine.scan_code(code, "python", "note.py") == []

    def test_empty_code_returns_empty(self):
        assert SASTEngine().scan_code("", "python", "x.py") == []

    def test_line_numbers_are_recorded(self):
        engine = SASTEngine()
        code = "x = 1\ny = eval(data)\n"
        findings = engine.scan_code(code, "python", "x.py")
        evals = [f for f in findings if f.vulnerability_type == "code_injection"]
        assert evals and evals[0].line_start == 2


class TestLanguageScoping:
    def test_python_rule_not_applied_to_js(self):
        engine = SASTEngine()
        # os.system is a Python-scoped rule; a JS file must not trigger it.
        code = "os.system(cmd)\n"
        findings = engine.scan_code(code, "javascript", "x.js")
        assert all(f.vulnerability_type != "command_injection" for f in findings)

    def test_language_agnostic_rule_applies_everywhere(self):
        engine = SASTEngine()
        code = 'password = "hunter2secret"\n'
        for lang in ("python", "javascript", "java"):
            findings = engine.scan_code(code, lang, "f")
            assert any(f.vulnerability_type == "hardcoded_secret" for f in findings)


class TestConfidenceScoring:
    def test_user_input_marker_raises_confidence(self):
        engine = SASTEngine()
        with_input = engine.scan_code("v = eval(request.data)\n", "python", "a.py")
        without = engine.scan_code("v = eval(data)\n", "python", "a.py")
        ci = next(f for f in with_input if f.vulnerability_type == "code_injection")
        co = next(f for f in without if f.vulnerability_type == "code_injection")
        assert ci.confidence > co.confidence

    def test_confidence_clamped_to_range(self):
        engine = SASTEngine()
        findings = engine.scan_code("v = eval(request.argv)\n", "python", "a.py")
        for f in findings:
            assert 0.1 <= f.confidence <= 0.99


class TestSeverityMapping:
    def test_sql_injection_maps_to_critical(self):
        assert SASTEngine._map_severity("sql_injection", "low") == "critical"

    def test_unknown_type_falls_back_to_default(self):
        assert SASTEngine._map_severity("unknown_type", "medium") == "medium"


class TestMergeFindings:
    def test_overlapping_native_and_llm_become_hybrid(self):
        engine = SASTEngine()
        native = [
            RawFinding(
                vulnerability_type="sql_injection",
                severity="critical",
                description="n",
                file_path="db.py",
                line_start=10,
                source="native",
                confidence=0.7,
            )
        ]
        llm = [
            RawFinding(
                vulnerability_type="sql_injection",
                severity="high",
                description="l",
                file_path="db.py",
                line_start=10,
                source="llm",
                confidence=0.5,
            )
        ]
        merged = engine._merge_findings(native, llm)
        assert len(merged) == 1
        assert merged[0].source == "hybrid"
        assert merged[0].confidence > 0.7

    def test_distinct_llm_finding_is_appended(self):
        engine = SASTEngine()
        native = [
            RawFinding(
                vulnerability_type="sql_injection",
                severity="critical",
                description="n",
                file_path="db.py",
                line_start=10,
                source="native",
            )
        ]
        llm = [
            RawFinding(
                vulnerability_type="idor",
                severity="high",
                description="l",
                file_path="api.py",
                line_start=5,
                source="llm",
            )
        ]
        merged = engine._merge_findings(native, llm)
        assert len(merged) == 2
        assert {f.vulnerability_type for f in merged} == {"sql_injection", "idor"}
