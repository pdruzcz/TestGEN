"""Broken authorization / IDOR rule tests (Story 4.2)."""

from app.services.security_scan.sast_engine import SASTEngine

engine = SASTEngine()


def _types(code, lang):
    return {f.vulnerability_type for f in engine.scan_code(code, lang, "f")}


def test_python_idor_objects_get_request():
    assert "idor" in _types("obj = Document.objects.get(id=request.GET['id'])\n", "python")


def test_python_get_object_or_404_request():
    assert "idor" in _types("doc = get_object_or_404(Doc, pk=request.data['id'])\n", "python")


def test_python_allow_any_permission():
    assert "broken_authz" in _types("permission_classes = [AllowAny]\n", "python")


def test_java_find_by_id_request():
    assert "idor" in _types("var u = repo.findById(request.getId());\n", "java")


def test_js_auth_bypass_marker():
    assert "broken_authz" in _types("// TODO: add auth check here\n", "javascript")


def test_idor_cwe_mapping():
    findings = engine.scan_code("obj = Document.objects.get(id=request.GET['id'])\n", "python", "f")
    idor = next(f for f in findings if f.vulnerability_type == "idor")
    assert idor.cwe_id == "CWE-639"
