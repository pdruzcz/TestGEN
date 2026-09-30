"""XSS rule tests (Story 4.2) — per language."""

from app.services.security_scan.sast_engine import SASTEngine

engine = SASTEngine()


def _types(code, lang):
    return {f.vulnerability_type for f in engine.scan_code(code, lang, "f")}


def test_js_inner_html():
    assert "xss" in _types("el.innerHTML = userData;\n", "javascript")


def test_js_document_write():
    assert "xss" in _types("document.write(location.hash);\n", "javascript")


def test_react_dangerously_set_inner_html():
    assert "xss" in _types("<div dangerouslySetInnerHTML={{__html: data}} />\n", "typescript")


def test_vue_v_html():
    assert "xss" in _types('<span v-html="userInput"></span>\n', "javascript")


def test_python_template_safe_filter():
    assert "xss" in _types("{{ user_bio | safe }}\n", "python")


def test_java_response_writer():
    assert "xss" in _types("response.getWriter().write(userInput);\n", "java")


def test_csharp_html_raw():
    assert "xss" in _types("@Html.Raw(model.Comment)\n", "csharp")


def test_cwe_mapping():
    findings = engine.scan_code("el.innerHTML = userData;\n", "javascript", "f")
    xss = next(f for f in findings if f.vulnerability_type == "xss")
    assert xss.cwe_id == "CWE-79"
