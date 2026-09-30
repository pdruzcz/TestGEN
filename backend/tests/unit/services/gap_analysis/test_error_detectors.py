"""Unit tests for code error detectors — Epic 5, Story 5.4."""

import pytest

from app.models.code_error import ErrorCategory
from app.services.analysis.ast.ast_tree import ASTTree, ErrorNode
from app.services.analysis.ast.nodes import FunctionNode, ClassNode, ParameterNode
from app.services.gap_analysis.error_detectors import (
    ConformanceDetector,
    LogicDetector,
    SemanticDetector,
    SyntaxDetector,
)


def _make_tree(
    functions=None,
    classes=None,
    error_nodes=None,
    language="python",
) -> ASTTree:
    """Build a minimal ASTTree for testing."""
    return ASTTree(
        language=language,
        functions=functions or [],
        classes=classes or [],
        error_nodes=error_nodes or [],
    )


# ── SyntaxDetector ────────────────────────────────────────────────────────────


class TestSyntaxDetector:
    def test_no_errors_clean_tree(self):
        tree = _make_tree()
        detector = SyntaxDetector()
        result = detector.detect(tree, "app.py")
        assert result == []

    def test_error_nodes_produce_critical(self):
        tree = _make_tree(
            error_nodes=[
                ErrorNode(line_start=10, line_end=10, message="Syntax error at line 10"),
            ]
        )
        detector = SyntaxDetector()
        result = detector.detect(tree, "app.py")
        assert len(result) == 1
        assert result[0].category == ErrorCategory.SYNTAX
        assert result[0].severity == "critical"
        assert result[0].line_start == 10
        assert result[0].file_path == "app.py"
        assert result[0].rule_id == "SYNTAX_ERROR"

    def test_multiple_error_nodes(self):
        tree = _make_tree(
            error_nodes=[
                ErrorNode(line_start=5, line_end=5),
                ErrorNode(line_start=20, line_end=22),
            ]
        )
        detector = SyntaxDetector()
        result = detector.detect(tree, None)
        assert len(result) == 2


# ── LogicDetector ─────────────────────────────────────────────────────────────


class TestLogicDetector:
    def test_empty_function_detected(self):
        func = FunctionNode(name="stub", type="function", line_start=1, line_end=2, complexity=1)
        tree = _make_tree(functions=[func])
        detector = LogicDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "EMPTY_FUNCTION" for r in result)

    def test_non_empty_function_not_flagged(self):
        func = FunctionNode(name="real", type="function", line_start=1, line_end=20, complexity=5)
        tree = _make_tree(functions=[func])
        detector = LogicDetector()
        result = detector.detect(tree, "app.py")
        assert not any(r.rule_id == "EMPTY_FUNCTION" for r in result)

    def test_missing_return_detected(self):
        func = FunctionNode(
            name="get_value",
            type="function",
            line_start=1,
            line_end=5,
            complexity=1,
            return_type="str",
        )
        tree = _make_tree(functions=[func])
        detector = LogicDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "MISSING_RETURN" for r in result)

    def test_init_not_flagged_for_missing_return(self):
        func = FunctionNode(
            name="__init__",
            type="function",
            line_start=1,
            line_end=3,
            complexity=1,
            return_type="None",
        )
        tree = _make_tree(functions=[func])
        detector = LogicDetector()
        result = detector.detect(tree, "app.py")
        assert not any(r.rule_id == "MISSING_RETURN" for r in result)

    def test_high_complexity_detected(self):
        func = FunctionNode(
            name="complex_fn",
            type="function",
            line_start=1,
            line_end=100,
            complexity=20,
        )
        tree = _make_tree(functions=[func])
        detector = LogicDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "HIGH_COMPLEXITY" for r in result)

    def test_normal_complexity_not_flagged(self):
        func = FunctionNode(
            name="simple",
            type="function",
            line_start=1,
            line_end=10,
            complexity=3,
        )
        tree = _make_tree(functions=[func])
        detector = LogicDetector()
        result = detector.detect(tree, "app.py")
        assert not any(r.rule_id == "HIGH_COMPLEXITY" for r in result)


# ── SemanticDetector ──────────────────────────────────────────────────────────


class TestSemanticDetector:
    def test_missing_return_type_on_public_function(self):
        func = FunctionNode(name="compute", type="function", line_start=1, line_end=10)
        tree = _make_tree(functions=[func])
        detector = SemanticDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "MISSING_RETURN_TYPE" for r in result)

    def test_private_function_not_flagged(self):
        func = FunctionNode(name="_helper", type="function", line_start=1, line_end=5)
        tree = _make_tree(functions=[func])
        detector = SemanticDetector()
        result = detector.detect(tree, "app.py")
        assert result == []

    def test_missing_param_type_annotation(self):
        func = FunctionNode(
            name="process",
            type="function",
            line_start=1,
            line_end=5,
            return_type="void",
            parameters=[ParameterNode(name="data")],
        )
        tree = _make_tree(functions=[func])
        detector = SemanticDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "MISSING_PARAM_TYPE" for r in result)

    def test_self_param_not_flagged(self):
        func = FunctionNode(
            name="method",
            type="function",
            line_start=1,
            line_end=5,
            return_type="None",
            parameters=[ParameterNode(name="self")],
        )
        tree = _make_tree(functions=[func])
        detector = SemanticDetector()
        result = detector.detect(tree, "app.py")
        assert not any(r.rule_id == "MISSING_PARAM_TYPE" for r in result)


# ── ConformanceDetector ───────────────────────────────────────────────────────


class TestConformanceDetector:
    def test_missing_docstring_on_public_function(self):
        func = FunctionNode(name="public_fn", type="function", line_start=1, line_end=10)
        tree = _make_tree(functions=[func])
        detector = ConformanceDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "MISSING_DOCSTRING" for r in result)

    def test_function_with_docstring_not_flagged(self):
        func = FunctionNode(
            name="documented",
            type="function",
            line_start=1,
            line_end=10,
            docstring="Does something useful.",
        )
        tree = _make_tree(functions=[func])
        detector = ConformanceDetector()
        result = detector.detect(tree, "app.py")
        docstring_errors = [r for r in result if r.rule_id == "MISSING_DOCSTRING"]
        assert docstring_errors == []

    def test_missing_class_docstring(self):
        cls = ClassNode(name="MyClass", type="class", line_start=1, line_end=20)
        tree = _make_tree(classes=[cls])
        detector = ConformanceDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "MISSING_CLASS_DOCSTRING" for r in result)

    def test_non_snake_case_function_python(self):
        func = FunctionNode(name="BadName", type="function", line_start=1, line_end=5,
                           docstring="Has docstring.")
        tree = _make_tree(functions=[func], language="python")
        detector = ConformanceDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "NAMING_CONVENTION" for r in result)

    def test_non_snake_case_not_flagged_in_java(self):
        func = FunctionNode(name="camelCase", type="function", line_start=1, line_end=5,
                           docstring="Has docstring.")
        tree = _make_tree(functions=[func], language="java")
        detector = ConformanceDetector()
        result = detector.detect(tree, "App.java")
        assert not any(r.rule_id == "NAMING_CONVENTION" for r in result)

    def test_non_pascal_case_class_python(self):
        cls = ClassNode(name="lowercase_class", type="class", line_start=1, line_end=10,
                       docstring="Doc.")
        tree = _make_tree(classes=[cls], language="python")
        detector = ConformanceDetector()
        result = detector.detect(tree, "app.py")
        assert any(r.rule_id == "CLASS_NAMING_CONVENTION" for r in result)
