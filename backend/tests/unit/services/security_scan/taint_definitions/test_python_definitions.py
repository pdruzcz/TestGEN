"""Python taint definition tests (Story 4.3)."""

from app.services.security_scan.taint_definitions import (
    sanitizers_for_language,
    sinks_for_language,
    sources_for_language,
)
from app.services.security_scan.taint_definitions.python_definitions import (
    PY_SINKS,
    PY_SOURCES,
)


def test_request_source_matches():
    src = next(s for s in PY_SOURCES if s.name == "HTTP request data")
    assert src.matches("x = request.GET['q']")
    assert src.taint_type == "user_input"


def test_exec_sink_severity_critical():
    sink = next(s for s in PY_SINKS if s.sink_type == "exec" and "os.system" in s.name)
    assert sink.severity == "critical"
    assert sink.matches("os.system(cmd)")


def test_language_scoping_excludes_python_for_js_only():
    # A JS-only source (req.body) must not surface for python.
    py_sources = sources_for_language("python")
    assert all("req.body" not in s.patterns[0].pattern for s in py_sources)


def test_sanitizer_protects_against_sink_types():
    san = next(s for s in sanitizers_for_language("python") if "html.escape" in s.name)
    assert san.protects("html")
    assert not san.protects("sql")


def test_sinks_for_language_python_nonempty():
    assert len(sinks_for_language("python")) > 0
