"""Tests for CppAdapter (Story 1.19)."""

import pytest

from app.services.analysis.ast.adapters.cpp_parser import CppAdapter


@pytest.fixture
def parser():
    return CppAdapter()


# ── Function extraction ─────────────────────────────────────────────


class TestCppFunctions:
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
        assert len(fn.parameters) == 2
        assert fn.parameters[0].name == "a"

    def test_function_with_reference_param(self, parser):
        code = "void process(std::string &str) {\n    return;\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert len(fn.parameters) >= 1

    def test_multiple_functions(self, parser):
        code = "void foo() {}\nvoid bar() {}\nint baz() { return 1; }\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 3

    def test_class_methods_not_in_top_level(self, parser):
        code = "class Foo {\n    void bar() {}\n};\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 0
        assert len(tree.classes[0].methods) == 1

    def test_namespaced_function(self, parser):
        code = "namespace ns {\n    int helper() { return 42; }\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1


# ── Class extraction ────────────────────────────────────────────────


class TestCppClasses:
    def test_simple_class(self, parser):
        code = "class MyClass {\npublic:\n    void foo() {}\n};\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "MyClass"

    def test_class_with_inheritance(self, parser):
        code = "class Child : public Parent {\n};\n"
        tree = parser.parse(code)
        assert len(tree.classes[0].bases) >= 1

    def test_struct(self, parser):
        code = "struct Point {\n    int x;\n    int y;\n};\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "Point"
        assert tree.classes[0].type == "struct"

    def test_enum(self, parser):
        code = "enum class Color {\n    RED, GREEN, BLUE\n};\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1

    def test_class_methods(self, parser):
        code = (
            "class Foo {\n"
            "public:\n"
            "    Foo() {}\n"
            "    void bar() {}\n"
            "    ~Foo() {}\n"
            "};\n"
        )
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 3  # constructor + bar + destructor

    def test_nested_class(self, parser):
        code = "class Outer {\n    class Inner {\n    };\n};\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 2


# ── Import extraction ───────────────────────────────────────────────


class TestCppImports:
    def test_system_include(self, parser):
        code = "#include <iostream>\nint main() {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert "iostream" in tree.imports[0].module

    def test_local_include(self, parser):
        code = '#include "mylib.hpp"\nint main() {}\n'
        tree = parser.parse(code)
        assert tree.imports[0].module == "mylib.hpp"

    def test_multiple_includes(self, parser):
        code = "#include <iostream>\n#include <vector>\n#include <string>\nint main() {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 3


# ── Integration ─────────────────────────────────────────────────────


class TestCppAdapterIntegration:
    def test_registry_registered(self):
        from app.services.analysis.ast.registry import ASTParserRegistry

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("cpp")
        assert registry.is_supported("c++")

    def test_full_cpp_file(self, parser):
        code = (
            "#include <iostream>\n"
            "#include <vector>\n"
            "\n"
            "class Calculator {\n"
            "public:\n"
            "    int add(int a, int b) {\n"
            "        return a + b;\n"
            "    }\n"
            "};\n"
            "\n"
            "int main() {\n"
            "    Calculator calc;\n"
            "    return calc.add(1, 2);\n"
            "}\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 2
        assert len(tree.classes) == 1
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "main"

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
        assert parser.language == "cpp"
