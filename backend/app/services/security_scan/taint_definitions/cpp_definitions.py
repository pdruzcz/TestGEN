"""C/C++ taint definitions — Epic 4, Story 4.3."""

from app.services.security_scan.taint_definitions.base import (
    C,
    TaintSanitizer,
    TaintSink,
    TaintSource,
    rx,
)

CPP_SOURCES: tuple[TaintSource, ...] = (
    TaintSource(
        name="argv / command line",
        patterns=(rx(r"\bargv\s*\["), rx(r"\bargc\b")),
        language=C,
        taint_type="user_input",
    ),
    TaintSource(
        name="stdin read",
        patterns=(rx(r"\bfgets\s*\("), rx(r"\bscanf\s*\("), rx(r"\bgets\s*\(")),
        language=C,
        taint_type="user_input",
    ),
    TaintSource(
        name="environment variable",
        patterns=(rx(r"\bgetenv\s*\("),),
        language=C,
        taint_type="env_input",
    ),
)

CPP_SINKS: tuple[TaintSink, ...] = (
    TaintSink(
        name="system / popen (exec)",
        patterns=(rx(r"\bsystem\s*\("), rx(r"\bpopen\s*\("), rx(r"\bexecvp?\s*\(")),
        language=C,
        sink_type="exec",
        vulnerability_type="command_injection",
        cwe_id="CWE-78",
        severity="critical",
    ),
    TaintSink(
        name="sprintf / strcpy (buffer)",
        patterns=(rx(r"\bsprintf\s*\("), rx(r"\bstrcpy\s*\("), rx(r"\bstrcat\s*\(")),
        language=C,
        sink_type="exec",
        vulnerability_type="buffer_overflow",
        cwe_id="CWE-120",
        severity="critical",
    ),
    TaintSink(
        name="fopen (file path)",
        patterns=(rx(r"\bfopen\s*\("), rx(r"\bopen\s*\(")),
        language=C,
        sink_type="file",
        vulnerability_type="path_traversal",
        cwe_id="CWE-22",
        severity="medium",
    ),
)

CPP_SANITIZERS: tuple[TaintSanitizer, ...] = (
    TaintSanitizer(
        name="snprintf (bounded)",
        patterns=(rx(r"\bsnprintf\s*\("), rx(r"\bstrncpy\s*\("), rx(r"\bstrncat\s*\(")),
        language=C,
        protects_against=frozenset({"exec"}),
    ),
    TaintSanitizer(
        name="atoi / strtol (numeric)",
        patterns=(rx(r"\batoi\s*\("), rx(r"\bstrtol\s*\(")),
        language=C,
        protects_against=frozenset({"exec", "file"}),
    ),
)
