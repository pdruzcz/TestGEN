"""Tests for JavaAdapter (Story 1.16)."""

import pytest

from app.services.analysis.ast.adapters.java_parser import JavaAdapter


@pytest.fixture
def parser():
    return JavaAdapter()


# ── Method extraction ───────────────────────────────────────────────


class TestJavaMethods:
    def test_simple_method(self, parser):
        code = (
            "public class Foo {\n"
            "    public void bar() {\n"
            "        System.out.println(\"hello\");\n"
            "    }\n"
            "}\n"
        )
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 1
        assert cls.methods[0].name == "bar"
        assert cls.methods[0].return_type == "void"

    def test_method_with_params(self, parser):
        code = (
            "class Foo {\n"
            "    public String greet(String name, int age) {\n"
            "        return name;\n"
            "    }\n"
            "}\n"
        )
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert len(method.parameters) == 2
        assert method.parameters[0].name == "name"
        assert method.parameters[0].type == "String"
        assert method.parameters[1].name == "age"
        assert method.parameters[1].type == "int"
        assert method.return_type == "String"

    def test_class_methods_not_in_top_level_functions(self, parser):
        code = "class Foo {\n    void bar() {}\n}\n"
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
        assert cls.methods[0].parameters[0].type == "int"

    def test_multiple_methods(self, parser):
        code = (
            "class Foo {\n"
            "    void a() {}\n"
            "    void b() {}\n"
            "    void c() {}\n"
            "}\n"
        )
        tree = parser.parse(code)
        assert len(tree.classes[0].methods) == 3

    def test_method_line_numbers(self, parser):
        code = "class Foo {\n    void bar() {\n        return;\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.line_start == 2
        assert method.line_end == 4

    def test_static_method(self, parser):
        code = "class Foo {\n    public static void main(String[] args) {}\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.name == "main"
        assert len(method.parameters) == 1

    def test_abstract_method(self, parser):
        code = "abstract class Foo {\n    abstract void execute();\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 1
        assert cls.methods[0].name == "execute"

    def test_annotated_method(self, parser):
        code = "class Foo {\n    @Override\n    public String toString() {\n        return \"foo\";\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.name == "toString"
        assert method.return_type == "String"

    def test_generic_return_type(self, parser):
        code = "class Foo {\n    public List<String> getNames() {\n        return null;\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert "List" in method.return_type


# ── Class extraction ────────────────────────────────────────────────


class TestJavaClasses:
    def test_simple_class(self, parser):
        code = "public class MyClass {\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "MyClass"

    def test_class_with_extends(self, parser):
        code = "class Child extends Parent {\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert "Parent" in cls.bases

    def test_class_with_implements(self, parser):
        code = "class Foo implements Runnable, Serializable {\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.bases) >= 2

    def test_interface_with_methods(self, parser):
        code = "public interface IService {\n    void execute();\n    String getName();\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert cls.name == "IService"
        assert len(cls.methods) == 2

    def test_interface_extends(self, parser):
        code = "interface Foo extends Bar, Baz {\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.bases) >= 1

    def test_enum(self, parser):
        code = "public enum Color {\n    RED, GREEN, BLUE\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "Color"

    def test_nested_class(self, parser):
        code = "class Outer {\n    class Inner {\n    }\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 2

    def test_class_line_numbers(self, parser):
        code = "\nclass Foo {\n}\n"
        tree = parser.parse(code)
        assert tree.classes[0].line_start == 2


# ── Import extraction ───────────────────────────────────────────────


class TestJavaImports:
    def test_simple_import(self, parser):
        code = "import java.util.List;\nclass Foo {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert tree.imports[0].module == "java.util.List"

    def test_wildcard_import(self, parser):
        code = "import java.util.*;\nclass Foo {}\n"
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert "*" in imp.aliases
        assert imp.module == "java.util.*"

    def test_static_import(self, parser):
        code = "import static org.junit.Assert.assertEquals;\nclass Foo {}\n"
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert imp.module == "org.junit.Assert.assertEquals"

    def test_multiple_imports(self, parser):
        code = (
            "import java.util.List;\n"
            "import java.util.Map;\n"
            "import java.io.File;\n"
            "class Foo {}\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 3


# ── Integration ─────────────────────────────────────────────────────


class TestJavaAdapterIntegration:
    def test_registry_registered(self):
        from app.services.analysis.ast.registry import ASTParserRegistry

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("java")

    def test_full_java_file(self, parser):
        code = (
            "package com.example;\n"
            "\n"
            "import java.util.List;\n"
            "import java.util.ArrayList;\n"
            "\n"
            "public class UserService {\n"
            "    private String name;\n"
            "\n"
            "    public UserService(String name) {\n"
            "        this.name = name;\n"
            "    }\n"
            "\n"
            "    public String getName() {\n"
            "        return name;\n"
            "    }\n"
            "\n"
            "    public List<String> getNames() {\n"
            "        return new ArrayList<>();\n"
            "    }\n"
            "}\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 2
        assert len(tree.classes) == 1
        cls = tree.classes[0]
        assert cls.name == "UserService"
        assert len(cls.methods) == 3
        # Verify generic return type works
        get_names = [m for m in cls.methods if m.name == "getNames"][0]
        assert "List" in get_names.return_type

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
        assert parser.language == "java"
