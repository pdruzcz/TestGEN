"""Tests for CSharpAdapter (Story 1.18)."""

import pytest

from app.services.analysis.ast.adapters.csharp_parser import CSharpAdapter


@pytest.fixture
def parser():
    return CSharpAdapter()


# ── Method extraction ───────────────────────────────────────────────


class TestCSharpMethods:
    def test_simple_method(self, parser):
        code = (
            "class Foo {\n"
            "    public void Bar() {\n"
            "        Console.WriteLine(\"hello\");\n"
            "    }\n"
            "}\n"
        )
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 1
        assert cls.methods[0].name == "Bar"
        assert cls.methods[0].return_type == "void"

    def test_method_with_params(self, parser):
        code = "class Foo {\n    public string Greet(string name, int age) {\n        return name;\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert len(method.parameters) == 2
        assert method.parameters[0].name == "name"
        assert method.parameters[0].type == "string"
        assert method.parameters[1].type == "int"
        assert method.return_type == "string"

    def test_class_methods_not_in_top_level(self, parser):
        code = "class Foo {\n    void Bar() {}\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 0
        assert len(tree.classes[0].methods) == 1

    def test_constructor(self, parser):
        code = "class Foo {\n    public Foo(int x) {\n        this.x = x;\n    }\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 1
        assert cls.methods[0].name == "Foo"
        assert cls.methods[0].type == "constructor"

    def test_property(self, parser):
        code = "class Foo {\n    public string Name { get; set; }\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        props = [m for m in cls.methods if m.type == "property"]
        assert len(props) >= 1
        assert props[0].name == "Name"

    def test_static_method(self, parser):
        code = "class Foo {\n    public static void Main(string[] args) {}\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.name == "Main"

    def test_method_line_numbers(self, parser):
        code = "class Foo {\n    void Bar() {\n        return;\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.line_start == 2
        assert method.line_end == 4


# ── Class extraction ────────────────────────────────────────────────


class TestCSharpClasses:
    def test_simple_class(self, parser):
        code = "public class MyClass {\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "MyClass"

    def test_class_with_base(self, parser):
        code = "class Child : Parent {\n}\n"
        tree = parser.parse(code)
        assert "Parent" in tree.classes[0].bases

    def test_class_with_interface(self, parser):
        code = "class Foo : IBar, IBaz {\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes[0].bases) >= 2

    def test_interface(self, parser):
        code = "public interface IService {\n    void Execute();\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "IService"

    def test_struct(self, parser):
        code = "public struct Point {\n    public int X;\n    public int Y;\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "Point"

    def test_enum(self, parser):
        code = "public enum Color {\n    Red, Green, Blue\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "Color"

    def test_nested_class(self, parser):
        code = "class Outer {\n    class Inner {\n    }\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 2


# ── Import extraction ───────────────────────────────────────────────


class TestCSharpImports:
    def test_simple_using(self, parser):
        code = "using System;\nclass Foo {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert tree.imports[0].module == "System"

    def test_qualified_using(self, parser):
        code = "using System.Collections.Generic;\nclass Foo {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert "Collections" in tree.imports[0].module

    def test_static_using(self, parser):
        code = "using static System.Math;\nclass Foo {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1

    def test_multiple_usings(self, parser):
        code = "using System;\nusing System.IO;\nusing System.Linq;\nclass Foo {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 3


# ── Integration ─────────────────────────────────────────────────────


class TestCSharpAdapterIntegration:
    def test_registry_registered(self):
        from app.services.analysis.ast.registry import ASTParserRegistry

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("csharp")
        assert registry.is_supported("c#")

    def test_full_csharp_file(self, parser):
        code = (
            "using System;\n"
            "using System.Collections.Generic;\n"
            "\n"
            "namespace MyApp {\n"
            "    public class UserService {\n"
            "        private string name;\n"
            "\n"
            "        public UserService(string name) {\n"
            "            this.name = name;\n"
            "        }\n"
            "\n"
            "        public string GetName() {\n"
            "            return name;\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 2
        assert len(tree.classes) == 1
        cls = tree.classes[0]
        assert cls.name == "UserService"
        assert len(cls.methods) >= 2  # constructor + GetName

    def test_error_recovery(self, parser):
        code = "class Foo {\n    broken syntax\n}\n"
        tree = parser.parse(code)
        assert tree.has_errors()

    def test_empty_code(self, parser):
        tree = parser.parse("")
        assert tree.functions == []
        assert tree.classes == []
        assert tree.imports == []

    def test_language_property(self, parser):
        assert parser.language == "csharp"
