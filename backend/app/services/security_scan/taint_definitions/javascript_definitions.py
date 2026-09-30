"""JavaScript/TypeScript taint definitions — Epic 4, Story 4.3."""

from app.services.security_scan.taint_definitions.base import (
    JS,
    TaintSanitizer,
    TaintSink,
    TaintSource,
    rx,
)

JS_SOURCES: tuple[TaintSource, ...] = (
    TaintSource(
        name="request body / params",
        patterns=(rx(r"req\.(body|params|query|cookies|headers)"),),
        language=JS,
        taint_type="user_input",
    ),
    TaintSource(
        name="DOM / location input",
        patterns=(
            rx(r"location\.(hash|search|href)"),
            rx(r"document\.cookie"),
            rx(r"window\.name"),
        ),
        language=JS,
        taint_type="user_input",
    ),
    TaintSource(
        name="environment variable",
        patterns=(rx(r"process\.env\."),),
        language=JS,
        taint_type="env_input",
    ),
)

JS_SINKS: tuple[TaintSink, ...] = (
    TaintSink(
        name="db query (SQL)",
        patterns=(rx(r"\.query\s*\("), rx(r"\.execute\s*\(")),
        language=JS,
        sink_type="sql",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        severity="high",
    ),
    TaintSink(
        name="innerHTML / document.write (HTML)",
        patterns=(
            rx(r"\.innerHTML\s*="),
            rx(r"\.outerHTML\s*="),
            rx(r"document\.write\s*\("),
        ),
        language=JS,
        sink_type="html",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        severity="medium",
    ),
    TaintSink(
        name="eval / Function (code)",
        patterns=(rx(r"\beval\s*\("), rx(r"new\s+Function\s*\(")),
        language=JS,
        sink_type="exec",
        vulnerability_type="code_injection",
        cwe_id="CWE-95",
        severity="critical",
    ),
    TaintSink(
        name="child_process exec",
        patterns=(rx(r"child_process\.exec\s*\("), rx(r"\bexec\s*\(")),
        language=JS,
        sink_type="exec",
        vulnerability_type="command_injection",
        cwe_id="CWE-78",
        severity="critical",
    ),
)

JS_SANITIZERS: tuple[TaintSanitizer, ...] = (
    TaintSanitizer(
        name="DOMPurify.sanitize",
        patterns=(rx(r"DOMPurify\.sanitize\s*\("),),
        language=JS,
        protects_against=frozenset({"html"}),
    ),
    TaintSanitizer(
        name="escapeHtml",
        patterns=(rx(r"escapeHtml\s*\("), rx(r"escape\s*\(")),
        language=JS,
        protects_against=frozenset({"html"}),
    ),
    TaintSanitizer(
        name="parseInt / Number",
        patterns=(rx(r"parseInt\s*\("), rx(r"Number\s*\(")),
        language=JS,
        protects_against=frozenset({"sql", "exec", "html"}),
    ),
)
