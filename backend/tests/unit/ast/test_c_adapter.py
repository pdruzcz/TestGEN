"""Tests for CAdapter (Story 1.19)."""

import pytest

from app.services.analysis.ast.adapters.c_adapter import CAdapter


@pytest.fixture
def parser():
    return CAdapter()


# ── Function extraction ─────────────────────────────────────────────


class TestCFunctions:
    def test_simple_function(self, parser):
        code = "int main() {\n    return 0;\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "main"
        assert tree.functions[0].return_type == "int"

    def test_function_with_params(self, parser):
        code = "int add(int a, int b) {\n    return a + b;\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert fn.name == "add"
        assert len(fn.parameters) == 2
        assert fn.parameters[0].name == "a"
        assert fn.parameters[0].type == "int"

    def test_function_with_pointer_param(self, parser):
        code = "void process(char *str, int len) {\n    return;\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert len(fn.parameters) == 2

    def test_void_function(self, parser):
        code = "void hello() {\n    printf(\"hello\");\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert fn.name == "hello"
        assert fn.return_type == "void"

    def test_multiple_functions(self, parser):
        code = "void foo() {}\nvoid bar() {}\nint baz() { return 1; }\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 3

    def test_function_line_numbers(self, parser):
        code = "#include <stdio.h>\n\nint main() {\n    return 0;\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert fn.line_start == 3

    def test_static_function(self, parser):
        code = "static int helper() {\n    return 42;\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "helper"


# ── Struct/enum extraction ──────────────────────────────────────────


class TestCStructs:
    def test_simple_struct(self, parser):
        code = "struct Point {\n    int x;\n    int y;\n};\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "Point"
        assert tree.classes[0].type == "struct"

    def test_enum(self, parser):
        code = "enum Color {\n    RED, GREEN, BLUE\n};\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "Color"
        assert tree.classes[0].type == "enum"

    def test_typedef_struct(self, parser):
        code = "typedef struct {\n    int x;\n    int y;\n} Point;\n"
        tree = parser.parse(code)
        assert len(tree.classes) >= 1

    def test_struct_line_numbers(self, parser):
        code = "\nstruct Foo {\n    int a;\n};\n"
        tree = parser.parse(code)
        assert tree.classes[0].line_start == 2


# ── Import extraction ───────────────────────────────────────────────


class TestCImports:
    def test_system_include(self, parser):
        code = "#include <stdio.h>\nint main() { return 0; }\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert "stdio" in tree.imports[0].module

    def test_local_include(self, parser):
        code = '#include "mylib.h"\nint main() { return 0; }\n'
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert tree.imports[0].module == "mylib.h"

    def test_multiple_includes(self, parser):
        code = "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\nint main() {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 3


# ── Integration ─────────────────────────────────────────────────────


class TestCAdapterIntegration:
    def test_registry_registered(self):
        from app.services.analysis.ast.registry import ASTParserRegistry

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("c")

    def test_full_c_file(self, parser):
        code = (
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "\n"
            "struct Point {\n"
            "    int x;\n"
            "    int y;\n"
            "};\n"
            "\n"
            "int main(int argc, char **argv) {\n"
            "    printf(\"hello\");\n"
            "    return 0;\n"
            "}\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 2
        assert len(tree.classes) == 1
        assert len(tree.functions) == 1

    def test_error_recovery(self, parser):
        code = "int foo( {\n    broken\n"
        tree = parser.parse(code)
        assert tree.has_errors()

    def test_empty_code(self, parser):
        tree = parser.parse("")
        assert tree.functions == []
        assert tree.classes == []
        assert tree.imports == []

    def test_language_property(self, parser):
        assert parser.language == "c"
