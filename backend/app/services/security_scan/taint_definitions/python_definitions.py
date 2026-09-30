"""Python taint definitions — Epic 4, Story 4.3."""

from app.services.security_scan.taint_definitions.base import (
    PY,
    TaintSanitizer,
    TaintSink,
    TaintSource,
    rx,
)

PY_SOURCES: tuple[TaintSource, ...] = (
    TaintSource(
        name="HTTP request data",
        patterns=(rx(r"request\.(GET|POST|args|form|values|data|json|cookies|headers)"),),
        language=PY,
        taint_type="user_input",
    ),
    TaintSource(
        name="stdin / argv",
        patterns=(rx(r"\binput\s*\("), rx(r"sys\.argv")),
        language=PY,
        taint_type="user_input",
    ),
    TaintSource(
        name="environment variable",
        patterns=(rx(r"os\.environ"), rx(r"os\.getenv\s*\(")),
        language=PY,
        taint_type="env_input",
    ),
    TaintSource(
        name="file read",
        patterns=(rx(r"\.read\s*\(\s*\)"), rx(r"\.readline\s*\(")),
        language=PY,
        taint_type="file_input",
    ),
)

PY_SINKS: tuple[TaintSink, ...] = (
    TaintSink(
        name="cursor.execute (SQL)",
        patterns=(rx(r"\.execute\s*\("), rx(r"\.executemany\s*\(")),
        language=PY,
        sink_type="sql",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        severity="high",
    ),
    TaintSink(
        name="os.system / subprocess (exec)",
        patterns=(rx(r"os\.system\s*\("), rx(r"subprocess\.(call|run|Popen)\s*\(")),
        language=PY,
        sink_type="exec",
        vulnerability_type="command_injection",
        cwe_id="CWE-78",
        severity="critical",
    ),
    TaintSink(
        name="eval / exec (code)",
        patterns=(rx(r"\beval\s*\("), rx(r"\bexec\s*\(")),
        language=PY,
        sink_type="exec",
        vulnerability_type="code_injection",
        cwe_id="CWE-95",
        severity="critical",
    ),
    TaintSink(
        name="template render (HTML)",
        patterns=(rx(r"render_template_string\s*\("), rx(r"\bMarkup\s*\(")),
        language=PY,
        sink_type="html",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        severity="medium",
    ),
    TaintSink(
        name="open (file path)",
        patterns=(rx(r"\bopen\s*\("),),
        language=PY,
        sink_type="file",
        vulnerability_type="path_traversal",
        cwe_id="CWE-22",
        severity="medium",
    ),
)

PY_SANITIZERS: tuple[TaintSanitizer, ...] = (
    TaintSanitizer(
        name="html.escape / markupsafe.escape",
        patterns=(rx(r"html\.escape\s*\("), rx(r"\bescape\s*\(")),
        language=PY,
        protects_against=frozenset({"html"}),
    ),
    TaintSanitizer(
        name="bleach.clean",
        patterns=(rx(r"bleach\.clean\s*\("),),
        language=PY,
        protects_against=frozenset({"html"}),
    ),
    TaintSanitizer(
        name="int / float cast",
        patterns=(rx(r"\bint\s*\("), rx(r"\bfloat\s*\(")),
        language=PY,
        protects_against=frozenset({"sql", "exec", "file"}),
    ),
    TaintSanitizer(
        name="shlex.quote",
        patterns=(rx(r"shlex\.quote\s*\("),),
        language=PY,
        protects_against=frozenset({"exec"}),
    ),
)
