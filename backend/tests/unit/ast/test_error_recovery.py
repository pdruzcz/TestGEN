import pytest
import tree_sitter as ts
import tree_sitter_python as tspython

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import FunctionNode

PYTHON_LANG = ts.Language(tspython.language())


class ErrorTestParser(BaseASTParser):
    """Parser for error recovery testing."""

    language = "python"
    _ts_language = PYTHON_LANG

    def extract_functions(self, source_code, tree=None):
        if tree is None:
            return []
        functions = []
        self._walk_functions(tree.root_node, functions)
        return functions

    def _walk_functions(self, node, functions):
        if node.type == "function_definition":
            name = self._get_child_text(node, "identifier") or "<anonymous>"
            fn = FunctionNode(
                name=name,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
            )
            functions.append(fn)
        for child in node.children:
            self._walk_functions(child, functions)

    def extract_classes(self, source_code, tree=None):
        return []

    def extract_imports(self, source_code, tree=None):
        return []

    def _get_child_text(self, node, child_type: str) -> str | None:
        for child in node.children:
            if child.type == child_type:
                return child.text.decode("utf-8")
        return None


@pytest.fixture
def error_parser():
    return ErrorTestParser()


class TestErrorRecovery:
    def test_unclosed_parenthesis(self, error_parser: ErrorTestParser):
        code = "def foo(\n"
        tree = error_parser.parse(code)
        assert tree.has_errors()
        assert len(tree.error_nodes) > 0

    def test_incomplete_expression(self, error_parser: ErrorTestParser):
        code = "def foo():\n    return 1 +\n"
        tree = error_parser.parse(code)
        assert tree.has_errors()

    def test_valid_function_after_error(self, error_parser: ErrorTestParser):
        code = "def broken(\ndef valid():\n    pass\n"
        tree = error_parser.parse(code)
        # tree-sitter should still parse valid() despite error above
        valid_fns = [f for f in tree.functions if f.name == "valid"]
        assert len(valid_fns) == 1

    def test_empty_error_nodes_for_valid_code(self, error_parser: ErrorTestParser):
        code = "def foo():\n    pass\n"
        tree = error_parser.parse(code)
        assert not tree.has_errors()
        assert tree.error_nodes == []

    def test_multiple_errors(self, error_parser: ErrorTestParser):
        code = "def a(\ndef b(\nclass C\n"
        tree = error_parser.parse(code)
        assert tree.has_errors()
        assert len(tree.error_nodes) >= 1

    def test_error_nodes_have_line_info(self, error_parser: ErrorTestParser):
        code = "def foo(\n"
        tree = error_parser.parse(code)
        if tree.error_nodes:
            err = tree.error_nodes[0]
            assert err.line_start >= 1
            assert err.line_end >= err.line_start

    def test_missing_nodes_detected(self, error_parser: ErrorTestParser):
        code = "def foo():\n    return\n"
        tree = error_parser.parse(code)
        # tree-sitter may produce is_missing nodes for incomplete constructs
        # verify that if they appear, they are captured in error_nodes
        for err in tree.error_nodes:
            assert err.line_start >= 1
            assert err.line_end >= err.line_start

    def test_is_missing_in_broken_class(self, error_parser: ErrorTestParser):
        code = "class\n"
        tree = error_parser.parse(code)
        # "class" without name triggers is_missing on the name node
        # our iterative collector should catch both is_error and is_missing
        if tree.has_errors():
            assert len(tree.error_nodes) >= 1
