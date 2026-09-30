import time

import tree_sitter as ts
import tree_sitter_python as tspython

from app.services.analysis.ast.ast_tree import ASTTree
from app.services.analysis.ast.base_parser import BaseASTParser

PYTHON_LANG = ts.Language(tspython.language())

PERFORMANCE_THRESHOLD_MS = 1000  # < 1s for 10 000 LOC


class PerfTestParser(BaseASTParser):
    """Minimal parser for performance testing."""

    language = "python"
    _ts_language = PYTHON_LANG

    def extract_functions(self, source_code, tree=None):
        return []

    def extract_classes(self, source_code, tree=None):
        return []

    def extract_imports(self, source_code, tree=None):
        return []


def generate_large_python_code(loc: int = 10_000) -> str:
    """Generate a Python file with approximately `loc` lines."""
    lines = ["# Auto-generated performance test file"]
    for i in range(loc - 1):
        lines.append(f"x_{i} = {i}")
    return "\n".join(lines)


class TestPerformance:
    def test_parse_10k_loc_under_1s(self):
        code = generate_large_python_code(10_000)
        parser = PerfTestParser()

        start = time.time()
        tree = parser.parse(code)
        elapsed_ms = (time.time() - start) * 1000

        assert isinstance(tree, ASTTree)
        assert tree.loc_count == 10_000
        assert elapsed_ms < PERFORMANCE_THRESHOLD_MS, (
            f"Parsing took {elapsed_ms:.1f}ms, exceeds {PERFORMANCE_THRESHOLD_MS}ms threshold"
        )

    def test_parse_time_recorded(self):
        code = generate_large_python_code(1000)
        parser = PerfTestParser()
        tree = parser.parse(code)
        assert tree.parse_time_ms > 0
        assert tree.parse_time_ms < PERFORMANCE_THRESHOLD_MS
