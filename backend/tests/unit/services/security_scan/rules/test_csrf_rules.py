"""CSRF rule tests (Story 4.2) — explicit-disable signals."""

from app.services.security_scan.sast_engine import SASTEngine

engine = SASTEngine()


def _types(code, lang):
    return {f.vulnerability_type for f in engine.scan_code(code, lang, "f")}


def test_python_csrf_exempt_decorator():
    assert "csrf" in _types("@csrf_exempt\ndef view(request): ...\n", "python")


def test_python_wtf_csrf_disabled():
    assert "csrf" in _types("WTF_CSRF_ENABLED = False\n", "python")


def test_java_spring_csrf_disable():
    assert "csrf" in _types("http.csrf().disable();\n", "java")


def test_js_csrf_false():
    assert "csrf" in _types("app.use(csurf({ csrf: false }));\n", "javascript")


def test_csrf_cwe_mapping():
    findings = engine.scan_code("http.csrf().disable();\n", "java", "f")
    csrf = next(f for f in findings if f.vulnerability_type == "csrf")
    assert csrf.cwe_id == "CWE-352"
    assert csrf.owasp_category == "A01:2021-Broken Access Control"
