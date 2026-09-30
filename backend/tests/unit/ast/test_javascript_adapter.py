"""Tests for JavaScriptAdapter (Story 1.17)."""

import pytest

from app.services.analysis.ast.adapters.javascript_parser import JavaScriptAdapter


@pytest.fixture
def parser():
    return JavaScriptAdapter()


# ── Function extraction ─────────────────────────────────────────────


class TestJSFunctions:
    def test_function_declaration(self, parser):
        code = "function hello() {\n  console.log('hi');\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "hello"

    def test_arrow_function(self, parser):
        code = "const add = (a, b) => a + b;\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "add"

    def test_anonymous_function(self, parser):
        code = "const fn = function() { return 1; };\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1

    def test_function_with_params(self, parser):
        code = "function greet(name, age) {\n  return name;\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert len(fn.parameters) == 2
        assert fn.parameters[0].name == "name"

    def test_function_default_params(self, parser):
        code = "function foo(x = 10) {\n  return x;\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions[0].parameters) == 1
        assert tree.functions[0].parameters[0].name == "x"

    def test_function_rest_params(self, parser):
        code = "function foo(...args) {\n  return args;\n}\n"
        tree = parser.parse(code)
        param_names = [p.name for p in tree.functions[0].parameters]
        assert "...args" in param_names

    def test_class_methods_not_in_functions(self, parser):
        code = "class Foo {\n  bar() { return 1; }\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 0
        assert len(tree.classes[0].methods) == 1

    def test_generator_function(self, parser):
        code = "function* gen() {\n  yield 1;\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "gen"


# ── Class extraction ────────────────────────────────────────────────


class TestJSClasses:
    def test_simple_class(self, parser):
        code = "class MyClass {\n  constructor() {}\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "MyClass"

    def test_class_with_extends(self, parser):
        code = "class Child extends Parent {\n}\n"
        tree = parser.parse(code)
        assert "Parent" in tree.classes[0].bases

    def test_class_methods(self, parser):
        code = "class Foo {\n  bar() {}\n  baz() {}\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 2
        names = {m.name for m in cls.methods}
        assert names == {"bar", "baz"}

    def test_class_method_params(self, parser):
        code = "class Foo {\n  bar(x, y) { return x + y; }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert len(method.parameters) == 2

    def test_class_getter_setter(self, parser):
        code = "class Foo {\n  get name() { return this._name; }\n  set name(v) { this._name = v; }\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 2
        names = {m.name for m in cls.methods}
        assert "name" in names

    def test_static_method(self, parser):
        code = "class Foo {\n  static create() { return new Foo(); }\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes[0].methods) == 1
        assert tree.classes[0].methods[0].name == "create"


# ── Import extraction ───────────────────────────────────────────────


class TestJSImports:
    def test_default_import(self, parser):
        code = 'import React from "react";\n'
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert tree.imports[0].module == "react"
        assert "React" in tree.imports[0].aliases

    def test_named_import(self, parser):
        code = 'import { useState, useEffect } from "react";\n'
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert "useState" in imp.aliases
        assert "useEffect" in imp.aliases

    def test_namespace_import(self, parser):
        code = 'import * as fs from "fs";\n'
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert any("fs" in a for a in imp.aliases)

    def test_multiple_imports(self, parser):
        code = 'import "side-effects";\nimport foo from "bar";\n'
        tree = parser.parse(code)
        assert len(tree.imports) == 2


# ── Integration ─────────────────────────────────────────────────────


class TestJSAdapterIntegration:
    def test_registry_registered(self):
        from app.services.analysis.ast.registry import ASTParserRegistry

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("javascript")

    def test_full_js_file(self, parser):
        code = (
            'import React, { useState } from "react";\n'
            "\n"
            "class App extends React.Component {\n"
            "  constructor(props) {\n"
            "    super(props);\n"
            "  }\n"
            "  render() {\n"
            "    return null;\n"
            "  }\n"
            "}\n"
            "\n"
            "function helper() {\n"
            "  return 42;\n"
            "}\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "App"
        assert len(tree.classes[0].methods) == 2
        assert len(tree.functions) == 1

    def test_error_recovery(self, parser):
        code = "function foo( {\n  broken\n"
        tree = parser.parse(code)
        assert tree.has_errors()

    def test_empty_code(self, parser):
        tree = parser.parse("")
        assert tree.functions == []
        assert tree.classes == []

    def test_language_property(self, parser):
        assert parser.language == "javascript"
