"""JavaScript taint definition tests (Story 4.3)."""

from app.services.security_scan.taint_definitions import (
    sinks_for_language,
    sources_for_language,
)
from app.services.security_scan.taint_definitions.javascript_definitions import (
    JS_SINKS,
    JS_SOURCES,
)


def test_req_body_source_matches():
    src = next(s for s in JS_SOURCES if s.name == "request body / params")
    assert src.matches("const u = req.body.name")


def test_innerhtml_sink_is_html():
    sink = next(s for s in JS_SINKS if "innerHTML" in s.name)
    assert sink.sink_type == "html"
    assert sink.vulnerability_type == "xss"
    assert sink.matches("el.innerHTML = data")


def test_eval_sink_is_exec_critical():
    sink = next(s for s in JS_SINKS if s.sink_type == "exec" and "eval" in s.name)
    assert sink.severity == "critical"


def test_js_definitions_scoped_to_js():
    js_sources = sources_for_language("javascript")
    assert js_sources
    ts_sinks = sinks_for_language("typescript")
    assert ts_sinks  # JS group includes typescript
