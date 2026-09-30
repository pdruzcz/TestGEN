"""Tests for PythonAdapter (Story 1.15)."""

import pytest

from app.services.analysis.ast.adapters.python_parser import PythonAdapter


@pytest.fixture
def parser():
    return PythonAdapter()


# ── Function extraction ─────────────────────────────────────────────


class TestPythonFunctions:
    def test_simple_function(self, parser):
        code = "def hello():\n    pass\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "hello"

    def test_function_with_params(self, parser):
        code = "def greet(name: str, age: int = 30) -> str:\n    return name\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert fn.name == "greet"
        assert len(fn.parameters) == 2
        assert fn.parameters[0].name == "name"
        assert fn.parameters[0].type == "str"
        assert fn.parameters[1].name == "age"
        assert fn.parameters[1].type == "int"

    def test_function_return_type_stripped(self, parser):
        code = "def foo() -> str:\n    pass\n"
        tree = parser.parse(code)
        assert tree.functions[0].return_type == "str"

    def test_multiple_functions(self, parser):
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n\ndef baz():\n    pass\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 3
        names = {f.name for f in tree.functions}
        assert names == {"foo", "bar", "baz"}

    def test_nested_functions_not_duplicated_at_top_level(self, parser):
        code = "def outer():\n    def inner():\n        pass\n    pass\n"
        tree = parser.parse(code)
        # Only outer at top-level, inner is a child
        assert len(tree.functions) == 1
        outer = tree.functions[0]
        assert outer.name == "outer"
        assert len(outer.children) == 1
        assert outer.children[0].name == "inner"

    def test_function_with_decorator(self, parser):
        code = "@staticmethod\ndef my_method():\n    pass\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "my_method"

    def test_async_function(self, parser):
        code = "async def fetch_data():\n    pass\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "fetch_data"

    def test_function_with_args_kwargs(self, parser):
        code = "def func(*args, **kwargs):\n    pass\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        param_names = [p.name for p in fn.parameters]
        assert "*args" in param_names
        assert "**kwargs" in param_names

    def test_function_line_numbers(self, parser):
        code = "x = 1\n\ndef hello():\n    pass\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert fn.line_start == 3
        assert fn.line_end == 4

    def test_function_docstring(self, parser):
        code = 'def hello():\n    """Say hello."""\n    pass\n'
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert fn.docstring is not None
        assert "Say hello" in fn.docstring

    def test_function_complexity(self, parser):
        code = "def complex(x):\n    if x > 0:\n        pass\n    elif x < 0:\n        pass\n    else:\n        pass\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert fn.complexity >= 3  # 1 base + if + elif

    def test_parameter_default_value(self, parser):
        code = "def foo(x=42):\n    pass\n"
        tree = parser.parse(code)
        assert tree.functions[0].parameters[0].default_value == "42"

    def test_parameter_line_start(self, parser):
        code = "def foo(x, y):\n    pass\n"
        tree = parser.parse(code)
        for p in tree.functions[0].parameters:
            assert p.line_start is not None
            assert p.line_start >= 1


# ── Class extraction ────────────────────────────────────────────────


class TestPythonClasses:
    def test_simple_class(self, parser):
        code = "class MyClass:\n    pass\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "MyClass"

    def test_class_with_bases(self, parser):
        code = "class Child(Parent):\n    pass\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert "Parent" in cls.bases

    def test_class_with_multiple_bases(self, parser):
        code = "class Child(Base1, Base2):\n    pass\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.bases) == 2

    def test_class_with_generic_base(self, parser):
        code = "from typing import Generic, TypeVar\nT = TypeVar('T')\nclass Repo(Generic[T]):\n    pass\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.bases) >= 1
        assert any("Generic" in b for b in cls.bases)

    def test_class_methods_not_in_top_level_functions(self, parser):
        """Critical: class methods must NOT appear in tree.functions."""
        code = "class Foo:\n    def bar(self):\n        pass\n\ndef standalone():\n    pass\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "standalone"
        assert len(tree.classes[0].methods) == 1
        assert tree.classes[0].methods[0].name == "bar"

    def test_class_with_methods(self, parser):
        code = (
            "class MyClass:\n"
            "    def __init__(self):\n"
            "        pass\n"
            "\n"
            "    def method(self):\n"
            "        pass\n"
        )
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert len(cls.methods) == 2
        method_names = {m.name for m in cls.methods}
        assert method_names == {"__init__", "method"}

    def test_class_method_params(self, parser):
        code = "class Foo:\n    def bar(self, x: int) -> str:\n        pass\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        method = cls.methods[0]
        assert method.name == "bar"
        assert len(method.parameters) == 2
        assert method.return_type == "str"

    def test_class_docstring(self, parser):
        code = 'class MyClass:\n    """My class docstring."""\n    pass\n'
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert cls.docstring is not None
        assert "My class docstring" in cls.docstring

    def test_nested_class(self, parser):
        code = "class Outer:\n    class Inner:\n        pass\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 2

    def test_class_line_numbers(self, parser):
        code = "\nclass Foo:\n    pass\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert cls.line_start == 2


# ── Import extraction ───────────────────────────────────────────────


class TestPythonImports:
    def test_simple_import(self, parser):
        code = "import os\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert tree.imports[0].module == "os"

    def test_import_from(self, parser):
        code = "from os.path import join\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        imp = tree.imports[0]
        assert imp.module == "os.path"

    def test_import_from_multiple_names(self, parser):
        code = "from os.path import join, exists, isfile\n"
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert "join" in imp.aliases
        assert "exists" in imp.aliases
        assert "isfile" in imp.aliases

    def test_import_with_alias(self, parser):
        code = "import numpy as np\n"
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert imp.module == "numpy"
        assert "np" in imp.aliases

    def test_import_from_wildcard(self, parser):
        code = "from os import *\n"
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert "*" in imp.aliases

    def test_multiple_imports(self, parser):
        code = "import os\nimport sys\nfrom pathlib import Path\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 3

    def test_import_line_numbers(self, parser):
        code = "x = 1\nimport os\n"
        tree = parser.parse(code)
        assert tree.imports[0].line_start == 2

    def test_multi_module_import(self, parser):
        """import os, sys should produce 2 separate ImportNodes."""
        code = "import os, sys\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 2
        modules = {imp.module for imp in tree.imports}
        assert modules == {"os", "sys"}


# ── Integration / edge cases ────────────────────────────────────────


class TestPythonAdapterIntegration:
    def test_registry_registered(self):
        from app.services.analysis.ast.registry import ASTParserRegistry

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("python")

    def test_parse_full_file(self, parser):
        code = (
            "import os\n"
            "from typing import List\n"
            "\n"
            "class Calculator:\n"
            '    """A simple calculator."""\n'
            "\n"
            "    def add(self, a: int, b: int) -> int:\n"
            "        return a + b\n"
            "\n"
            "    def multiply(self, a: int, b: int) -> int:\n"
            "        return a * b\n"
            "\n"
            "def main():\n"
            "    calc = Calculator()\n"
            "    return calc.add(1, 2)\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 2
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "Calculator"
        assert len(tree.classes[0].methods) == 2
        # Only `main` at top-level, class methods stay in class
        assert len(tree.functions) == 1
        assert tree.functions[0].name == "main"
        assert not tree.has_errors()

    def test_error_recovery(self, parser):
        code = "def foo(\n  broken syntax\n\n"
        tree = parser.parse(code)
        assert tree.has_errors()

    def test_empty_code(self, parser):
        tree = parser.parse("")
        assert tree.functions == []
        assert tree.classes == []
        assert tree.imports == []
        assert tree.loc_count == 1

    def test_parse_preserves_loc(self, parser):
        code = "line1\nline2\nline3\n"
        tree = parser.parse(code)
        assert tree.loc_count == 3

    def test_language_property(self, parser):
        assert parser.language == "python"
