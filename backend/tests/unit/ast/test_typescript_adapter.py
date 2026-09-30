"""Tests for TypeScriptAdapter (Story 1.17)."""

import pytest

from app.services.analysis.ast.adapters.typescript_parser import TypeScriptAdapter


@pytest.fixture
def parser():
    return TypeScriptAdapter()


# ── Function extraction ─────────────────────────────────────────────


class TestTSFunctions:
    def test_function_declaration(self, parser):
        code = "function hello(name: string): void {\n  console.log(name);\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "hello"
        assert tree.functions[0].return_type == "void"

    def test_function_with_typed_params(self, parser):
        code = "function add(a: number, b: number): number {\n  return a + b;\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert len(fn.parameters) == 2
        assert fn.parameters[0].name == "a"
        assert fn.parameters[0].type == "number"
        assert fn.return_type == "number"

    def test_arrow_function(self, parser):
        code = "const add = (a: number, b: number): number => a + b;\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "add"

    def test_optional_params(self, parser):
        code = "function foo(x?: string) {\n  return x;\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert len(fn.parameters) == 1

    def test_rest_params(self, parser):
        code = "function foo(...args: number[]) {\n  return args;\n}\n"
        tree = parser.parse(code)
        param_names = [p.name for p in tree.functions[0].parameters]
        assert any("args" in n for n in param_names)

    def test_class_methods_not_in_functions(self, parser):
        code = "class Foo {\n  bar(): void {}\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 0


# ── Class extraction ────────────────────────────────────────────────


class TestTSClasses:
    def test_simple_class(self, parser):
        code = "class MyClass {\n  constructor() {}\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "MyClass"

    def test_class_with_extends(self, parser):
        code = "class Child extends Parent {}\n"
        tree = parser.parse(code)
        assert "Parent" in tree.classes[0].bases

    def test_class_with_implements(self, parser):
        code = "class Foo implements IFoo, IBar {}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.bases) >= 2

    def test_interface(self, parser):
        code = "interface IUser {\n  getName(): string;\n  getAge(): number;\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "IUser"
        assert len(tree.classes[0].methods) == 2

    def test_class_methods_with_types(self, parser):
        code = "class Foo {\n  bar(x: number): string {\n    return x.toString();\n  }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.name == "bar"
        assert method.return_type == "string"

    def test_class_getter_setter(self, parser):
        code = "class Foo {\n  get name(): string { return this._name; }\n  set name(v: string) { this._name = v; }\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 2

    def test_static_method(self, parser):
        code = "class Foo {\n  static create(): Foo { return new Foo(); }\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes[0].methods) == 1
        assert tree.classes[0].methods[0].name == "create"


# ── Import extraction ───────────────────────────────────────────────


class TestTSImports:
    def test_default_import(self, parser):
        code = 'import React from "react";\n'
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert tree.imports[0].module == "react"

    def test_named_import(self, parser):
        code = 'import { useState, useEffect } from "react";\n'
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert "useState" in imp.aliases
        assert "useEffect" in imp.aliases

    def test_type_import(self, parser):
        code = 'import type { User } from "./types";\n'
        tree = parser.parse(code)
        assert len(tree.imports) == 1


# ── Integration ─────────────────────────────────────────────────────


class TestTSAdapterIntegration:
    def test_registry_registered(self):
        from app.services.analysis.ast.registry import ASTParserRegistry

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("typescript")

    def test_full_ts_file(self, parser):
        code = (
            'import { Component } from "react";\n'
            "\n"
            "interface Props {\n"
            "  name: string;\n"
            "}\n"
            "\n"
            "class App extends Component<Props> {\n"
            "  render(): void {\n"
            "    return null;\n"
            "  }\n"
            "}\n"
            "\n"
            "function helper(x: number): string {\n"
            "  return x.toString();\n"
            "}\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert len(tree.classes) == 2  # Props interface + App class
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
        assert parser.language == "typescript"
