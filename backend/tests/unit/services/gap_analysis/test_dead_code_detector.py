"""Unit tests for the dead code detector — Epic 5, Story 5.10.

AC1: private/internal functions and methods with zero project-wide calls
     are reported with location and "0 wywołań".
AC2: reachable elements are NOT reported (entry points, main, tests,
     dunders, imported names, framework handlers / decorators).
"""

from app.models.code_error import ErrorCategory
from app.services.analysis.ast.ast_tree import ASTTree
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
)
from app.services.gap_analysis.error_detectors.dead_code_detector import (
    DeadCodeDetector,
    ParsedFile,
    build_fingerprint,
)


def _fn(name: str, line_start: int, line_end: int) -> FunctionNode:
    return FunctionNode(name=name, type="function", line_start=line_start, line_end=line_end)


def _method(name: str, line_start: int, line_end: int) -> FunctionNode:
    return FunctionNode(name=name, type="function", line_start=line_start, line_end=line_end)


def _pf(
    file_path: str,
    content: str,
    functions=None,
    classes=None,
    imports=None,
) -> ParsedFile:
    """Build a ParsedFile with a manually constructed tree.

    Line numbers in the nodes MUST match ``content`` — the detector slices
    the source for fingerprints and looks above the def line for decorators.
    """
    tree = ASTTree(
        language="python",
        functions=functions or [],
        classes=classes or [],
        imports=imports or [],
    )
    return ParsedFile(tree=tree, file_path=file_path, content=content)


# ── AC1: uncalled private/internal code is reported ──────────────────────────


class TestDeadCodeReported:
    def test_private_function_never_called(self):
        pf = _pf(
            "app.py",
            "def _unused():\n    return 1\n",
            functions=[_fn("_unused", 1, 2)],
        )
        result = DeadCodeDetector().detect_project([pf])
        assert len(result) == 1
        r = result[0]
        assert r.category == ErrorCategory.DEAD_CODE
        assert r.rule_id == "DEAD_CODE"
        assert r.severity == "warning"
        assert r.file_path == "app.py"
        assert r.line_start == 1
        assert "_unused" in r.message
        assert "0 wywołań" in r.message
        assert r.context["calls"] == 0

    def test_private_method_never_called(self):
        pf = _pf(
            "svc.py",
            "class Svc:\n    def _helper(self):\n        return 2\n",
            classes=[
                ClassNode(
                    name="Svc",
                    type="class",
                    line_start=1,
                    line_end=3,
                    methods=[_method("_helper", 2, 3)],
                )
            ],
        )
        result = DeadCodeDetector().detect_project([pf])
        assert len(result) == 1
        assert result[0].context["function"] == "_helper"
        assert result[0].context["class"] == "Svc"

    def test_public_module_level_orphan_reported(self):
        """Module-level public function with 0 calls and no project import."""
        pf = _pf(
            "utils.py",
            "def orphan():\n    return 3\n",
            functions=[_fn("orphan", 1, 2)],
        )
        result = DeadCodeDetector().detect_project([pf])
        assert len(result) == 1
        assert result[0].context["function"] == "orphan"

    def test_cross_file_call_keeps_function_alive(self):
        """A call in ANOTHER file counts — reachability is project-wide."""
        defs = _pf(
            "lib.py",
            "def _validate(x):\n    return x\n",
            functions=[_fn("_validate", 1, 2)],
        )
        caller = _pf(
            "main_app.py",
            "from lib import _validate\n\ny = _validate(1)\n",
            imports=[
                ImportNode(
                    name="_validate", type="import", line_start=1, line_end=1, module="lib", aliases=["_validate"]
                )
            ],
        )
        result = DeadCodeDetector().detect_project([defs, caller])
        assert result == []

    def test_no_definitions_no_findings(self):
        pf = _pf("empty.py", "X = 1\n")
        assert DeadCodeDetector().detect_project([pf]) == []


# ── AC2: exclusions — reachable elements are not reported ────────────────────


class TestExclusions:
    def test_public_method_not_reported(self):
        """Public methods of classes are excluded in v1 (framework wiring,
        DI, reflection make them unreliably detectable)."""
        pf = _pf(
            "ctrl.py",
            "class Ctrl:\n    def handle(self):\n        return 1\n",
            classes=[
                ClassNode(
                    name="Ctrl",
                    type="class",
                    line_start=1,
                    line_end=3,
                    methods=[_method("handle", 2, 3)],
                )
            ],
        )
        assert DeadCodeDetector().detect_project([pf]) == []

    def test_main_and_dunders_excluded(self):
        pf = _pf(
            "run.py",
            "def main():\n    pass\n\n\ndef __str__(self):\n    return ''\n",
            functions=[_fn("main", 1, 2), _fn("__str__", 4, 5)],
        )
        assert DeadCodeDetector().detect_project([pf]) == []

    def test_constructor_excluded(self):
        pf = _pf(
            "model.py",
            "class M:\n    def __init__(self):\n        self.x = 1\n",
            classes=[
                ClassNode(
                    name="M",
                    type="class",
                    line_start=1,
                    line_end=3,
                    methods=[_method("__init__", 2, 3)],
                )
            ],
        )
        assert DeadCodeDetector().detect_project([pf]) == []

    def test_test_functions_excluded(self):
        pf = _pf(
            "test_flow.py",
            "def test_flow():\n    assert True\n",
            functions=[_fn("test_flow", 1, 2)],
        )
        assert DeadCodeDetector().detect_project([pf]) == []

    def test_whole_test_file_excluded(self):
        """Anything defined inside a test file is excluded, even private."""
        pf = _pf(
            "tests/test_helpers.py",
            "def _assert_custom():\n    assert True\n",
            functions=[_fn("_assert_custom", 1, 2)],
        )
        assert DeadCodeDetector().detect_project([pf]) == []

    def test_decorated_endpoint_excluded(self):
        """Framework handlers (route/endpoint/command decorators) are entry
        points even though nothing calls them explicitly."""
        content = '@app.get("/health")\ndef get_health():\n    return {"ok": True}\n'
        pf = _pf("api.py", content, functions=[_fn("get_health", 2, 3)])
        assert DeadCodeDetector().detect_project([pf]) == []

    def test_internal_decorator_excluded(self):
        """`@internal` is the documented way to keep intentional code out
        of the report."""
        content = "@internal\ndef _keep_me():\n    return 1\n"
        pf = _pf("keep.py", content, functions=[_fn("_keep_me", 2, 3)])
        assert DeadCodeDetector().detect_project([pf]) == []

    def test_imported_public_function_excluded(self):
        """Public module-level function imported anywhere in the project is
        reachable (imports heuristic)."""
        exported = _pf(
            "mod.py",
            "def exported_fn():\n    return 1\n",
            functions=[_fn("exported_fn", 1, 2)],
        )
        consumer = _pf(
            "other.py",
            "from mod import exported_fn\n",
            imports=[
                ImportNode(
                    name="exported_fn",
                    type="import",
                    line_start=1,
                    line_end=1,
                    module="mod",
                    aliases=["exported_fn"],
                )
            ],
        )
        assert DeadCodeDetector().detect_project([exported, consumer]) == []

    def test_spec_named_function_excluded(self):
        pf = _pf(
            "spec.py",
            "def validate_spec():\n    return 1\n",
            functions=[_fn("validate_spec", 1, 2)],
        )
        assert DeadCodeDetector().detect_project([pf]) == []


# ── Fingerprint (AC4 prerequisite): stable key {file}:{name}:{sha8} ───────────


class TestFingerprint:
    def test_fingerprint_on_finding(self):
        pf = _pf(
            "app.py",
            "def _unused():\n    return 1\n",
            functions=[_fn("_unused", 1, 2)],
        )
        r = DeadCodeDetector().detect_project([pf])[0]
        assert r.context["fingerprint"] == build_fingerprint("app.py", "_unused", "def _unused():\n    return 1\n")

    def test_same_code_same_fingerprint(self):
        src = "def _unused():\n    return 1\n"
        f1 = build_fingerprint("app.py", "_unused", src)
        f2 = build_fingerprint("app.py", "_unused", src)
        assert f1 == f2
        # format: file:name:sha8
        file_part, name_part, sha = f1.split(":")
        assert (file_part, name_part) == ("app.py", "_unused")
        assert len(sha) == 8

    def test_changed_body_changes_fingerprint(self):
        f1 = build_fingerprint("app.py", "_unused", "def _unused():\n    return 1\n")
        f2 = build_fingerprint("app.py", "_unused", "def _unused():\n    return 2\n")
        assert f1 != f2

    def test_moved_file_changes_fingerprint(self):
        f1 = build_fingerprint("a.py", "_unused", "def _unused():\n    return 1\n")
        f2 = build_fingerprint("b.py", "_unused", "def _unused():\n    return 1\n")
        assert f1 != f2


# ── Suggestion text (AC3) ─────────────────────────────────────────────────────


class TestSuggestion:
    def test_suggestion_mentions_internal(self):
        pf = _pf(
            "app.py",
            "def _unused():\n    return 1\n",
            functions=[_fn("_unused", 1, 2)],
        )
        r = DeadCodeDetector().detect_project([pf])[0]
        assert r.suggestion == "Sprawdź i usuń albo oznacz `@internal`"
