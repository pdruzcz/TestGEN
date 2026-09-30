import pytest
import tree_sitter as ts
import tree_sitter_python as tspython

from app.services.analysis.ast.ast_tree import ASTTree
from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import ClassNode, FunctionNode, ImportNode

PYTHON_LANG = ts.Language(tspython.language())


class ConcretePythonParser(BaseASTParser):
    """Minimal concrete parser for testing BaseASTParser."""

    language = "python"
    _ts_language = PYTHON_LANG

    def extract_functions(self, source_code: str, tree: ts.Tree | None = None) -> list[FunctionNode]:
        if tree is None:
            return []
        functions = []
        self._walk_functions(tree.root_node, functions)
        return functions

    def _walk_functions(self, node, functions: list[FunctionNode]):
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

    def extract_classes(self, source_code: str, tree: ts.Tree | None = None) -> list[ClassNode]:
        if tree is None:
            return []
        classes = []
        self._walk_classes(tree.root_node, classes)
        return classes

    def _walk_classes(self, node, classes: list[ClassNode]):
        if node.type == "class_definition":
            name = self._get_child_text(node, "identifier") or "Unknown"
            cls = ClassNode(
                name=name,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
            )
            classes.append(cls)
        for child in node.children:
            self._walk_classes(child, classes)

    def extract_imports(self, source_code: str, tree: ts.Tree | None = None) -> list[ImportNode]:
        if tree is None:
            return []
        imports = []
        self._walk_imports(tree.root_node, imports)
        return imports

    def _walk_imports(self, node, imports: list[ImportNode]):
        if node.type in ("import_statement", "import_from_statement"):
            imp = ImportNode(
                name=node.text.decode("utf-8"),
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
            )
            imports.append(imp)
        for child in node.children:
            self._walk_imports(child, imports)

    def _get_child_text(self, node, child_type: str) -> str | None:
        for child in node.children:
            if child.type == child_type:
                return child.text.decode("utf-8")
        return None


@pytest.fixture
def parser():
    return ConcretePythonParser()


class TestBaseASTParser:
    def test_parse_returns_ast_tree(self, parser: ConcretePythonParser):
        code = "def hello():\n    pass"
        tree = parser.parse(code)
        assert isinstance(tree, ASTTree)
        assert tree.language == "python"
        assert tree.loc_count == 2

    def test_parse_measures_time(self, parser: ConcretePythonParser):
        code = "x = 1\n"
        tree = parser.parse(code)
        assert tree.parse_time_ms >= 0

    def test_extract_functions(self, parser: ConcretePythonParser):
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 2
        assert tree.functions[0].name == "foo"
        assert tree.functions[1].name == "bar"

    def test_extract_classes(self, parser: ConcretePythonParser):
        code = "class MyClass:\n    pass\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "MyClass"

    def test_extract_imports(self, parser: ConcretePythonParser):
        code = "import os\nfrom sys import path\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 2

    def test_error_recovery_invalid_code(self, parser: ConcretePythonParser):
        code = "def foo(\n  broken syntax here\n\n"
        tree = parser.parse(code)
        # tree-sitter error recovery: should still return a tree, possibly with error_nodes
        assert isinstance(tree, ASTTree)
        # Error nodes should be present for broken syntax
        assert tree.has_errors()

    def test_parse_empty_code(self, parser: ConcretePythonParser):
        code = ""
        tree = parser.parse(code)
        assert isinstance(tree, ASTTree)
        assert tree.functions == []
        assert tree.classes == []
        assert tree.imports == []

    def test_parser_reuse(self, parser: ConcretePythonParser):
        """Parser can be reused for multiple parse calls."""
        tree1 = parser.parse("x = 1")
        tree2 = parser.parse("def foo(): pass")
        assert tree1.loc_count == 1
        assert len(tree2.functions) == 1

    def test_parse_with_source_path(self, parser: ConcretePythonParser):
        code = "def hello():\n    pass"
        tree = parser.parse(code, source_path="src/main.py")
        assert tree.source_path == "src/main.py"

    def test_parse_without_source_path(self, parser: ConcretePythonParser):
        code = "x = 1"
        tree = parser.parse(code)
        assert tree.source_path is None
