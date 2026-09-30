"""Taint analyzer tests (Story 4.3)."""

from app.services.security_scan.taint_analyzer import TaintAnalyzer

analyzer = TaintAnalyzer()


def _paths(code, lang):
    return analyzer.analyze_code(code, lang, "f")


def test_source_to_sql_sink_unsanitized():
    code = (
        "name = request.GET['name']\n"
        "query = 'SELECT * FROM u WHERE n=' + name\n"
        "cursor.execute(query)\n"
    )
    paths = _paths(code, "python")
    assert len(paths) == 1
    p = paths[0]
    assert p.vulnerability_type == "sql_injection"
    assert p.sink_type == "sql"
    assert p.sanitizer_adequate is True  # no sanitizer applied at all
    # full path: source -> transform -> sink
    types = [s.node_type for s in p.steps]
    assert types[0] == "source"
    assert types[-1] == "sink"


def test_exec_sink_is_critical():
    code = "cmd = input()\nos.system(cmd)\n"
    paths = _paths(code, "python")
    assert len(paths) == 1
    assert paths[0].severity == "critical"
    assert paths[0].sink_type == "exec"


def test_adequate_sanitizer_suppresses_finding():
    code = (
        "raw = request.GET['html']\n"
        "safe = html.escape(raw)\n"
        "render_template_string(safe)\n"
    )
    assert _paths(code, "python") == []


def test_inadequate_sanitizer_still_flagged():
    # html.escape protects HTML, not SQL — so the SQL sink is still vulnerable.
    code = (
        "raw = request.GET['id']\n"
        "safe = html.escape(raw)\n"
        "cursor.execute('SELECT ' + safe)\n"
    )
    paths = _paths(code, "python")
    assert len(paths) == 1
    assert paths[0].sink_type == "sql"
    assert paths[0].sanitizer_name is not None
    assert paths[0].sanitizer_adequate is False


def test_source_directly_in_sink():
    code = "os.system(request.GET['cmd'])\n"
    paths = _paths(code, "python")
    assert len(paths) == 1
    assert paths[0].sink_type == "exec"


def test_clean_code_no_paths():
    code = "x = 1\ny = x + 2\nprint(y)\n"
    assert _paths(code, "python") == []


def test_taint_path_steps_carry_metadata():
    code = "u = req.body.name\ndb.query('SELECT ' + u)\n"
    paths = _paths(code, "javascript")
    assert len(paths) == 1
    step = paths[0].steps[0]
    assert step.line == 1
    assert step.file_path == "f"
    assert step.node_type == "source"


def test_empty_code_returns_empty():
    assert _paths("", "python") == []
