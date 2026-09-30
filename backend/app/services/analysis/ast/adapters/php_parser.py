"""PHP AST parser adapter using tree-sitter.

Story 1.52 — Production PHP adapter extracting classes, interfaces, traits,
enums (PHP 8.1+), methods, functions, parameters, return types, namespaces
and ``use`` imports. Closes the FR12 PHP gap.

The tree-sitter-php grammar exposes ``language_php()`` (HTML + PHP, the
standard ``.php`` mode) rather than the ``language()`` entry point used by the
other grammars — see ``_PHP_LANG`` below.
"""

from __future__ import annotations

import tree_sitter as ts
import tree_sitter_php as tsphp

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
)
from app.services.analysis.ast.registry import register_parser

_PHP_LANG = ts.Language(tsphp.language_php())

# Node types to skip during traversal (string bodies / comments → no false positives).
_SKIP_TYPES = frozenset({"encapsed_string", "string", "string_value", "comment", "text"})

# PHP class-like declarations and their canonical ClassNode.type.
_CLASS_TYPES = frozenset({"class_declaration", "interface_declaration", "trait_declaration", "enum_declaration"})
_CLASS_TYPE_MAP = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "trait_declaration": "trait",
    "enum_declaration": "enum",
}

# Type-bearing node types (return types, parameter types). ``optional_type``
# is PHP's nullable form (``?array`` / ``?self``).
_TYPE_NODES = frozenset(
    {"named_type", "primitive_type", "union_type", "intersection_type", "optional_type", "list_type"}
)

# Body container node types (class/interface/trait vs. enum differ).
_BODY_TYPES = frozenset({"declaration_list", "enum_declaration_list"})


@register_parser("php")
class PhpAdapter(BaseASTParser):
    """Tree-sitter-based AST parser for PHP source code."""

    language = "php"
    _ts_language = _PHP_LANG

    # ── Function extraction ─────────────────────────────────────────

    def extract_functions(self, source_code: str, tree: ts.Tree | None = None) -> list[FunctionNode]:
        if tree is None:
            return []
        functions: list[FunctionNode] = []
        self._walk_functions(tree.root_node, functions)
        return functions

    def _walk_functions(self, node: ts.Node, out: list[FunctionNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        # Do not descend into class-like bodies — their functions are method_declaration,
        # collected as ClassNode.methods below.
        if node.type in _CLASS_TYPES:
            return
        if node.type == "function_definition":
            out.append(self._build_function_node(node))
            return
        for child in node.children:
            self._walk_functions(child, out)

    def _build_function_node(self, node: ts.Node) -> FunctionNode:
        name = self._child_text_by_field(node, "name") or "<anonymous>"
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        body = self._find_body(node)
        complexity = self._estimate_complexity(body) if body else 1

        return FunctionNode(
            name=name,
            type="function",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            parameters=params,
            return_type=return_type,
            complexity=complexity,
        )

    # ── Class extraction ────────────────────────────────────────────

    def extract_classes(self, source_code: str, tree: ts.Tree | None = None) -> list[ClassNode]:
        if tree is None:
            return []
        classes: list[ClassNode] = []
        self._walk_classes(tree.root_node, classes)
        return classes

    def _walk_classes(self, node: ts.Node, out: list[ClassNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        if node.type in _CLASS_TYPES:
            out.append(self._build_class_node(node))
            # Recurse into body for nested class-like declarations.
            body = self._find_body(node)
            if body:
                for child in body.children:
                    self._walk_classes(child, out)
            return
        for child in node.children:
            self._walk_classes(child, out)

    def _build_class_node(self, node: ts.Node) -> ClassNode:
        name = self._child_text_by_field(node, "name") or "Unknown"
        bases = self._extract_super_types(node)
        methods = self._extract_class_methods(node)
        complexity = sum(m.complexity for m in methods) if methods else 1

        return ClassNode(
            name=name,
            type=_CLASS_TYPE_MAP.get(node.type, "class"),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            complexity=complexity,
            methods=methods,
            bases=bases,
        )

    def _extract_super_types(self, node: ts.Node) -> list[str]:
        """Collect ``extends`` (base_clause) and ``implements`` (class_interface_clause) names."""
        bases: list[str] = []
        for child in node.children:
            if child.type == "base_clause":
                for sub in child.children:
                    if sub.is_named and sub.type not in ("extends",):
                        bases.append(sub.text.decode("utf-8"))
            elif child.type == "class_interface_clause":
                for sub in child.children:
                    if sub.is_named and sub.type not in ("implements", ","):
                        bases.append(sub.text.decode("utf-8"))
        return bases

    def _extract_class_methods(self, class_node: ts.Node) -> list[FunctionNode]:
        methods: list[FunctionNode] = []
        body = self._find_body(class_node)
        if body is None:
            return methods
        for child in body.children:
            if child.type == "method_declaration":
                methods.append(self._build_method_node(child))
        return methods

    def _build_method_node(self, node: ts.Node) -> FunctionNode:
        name = self._child_text_by_field(node, "name") or "<anonymous>"
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        body = self._find_body(node)
        complexity = self._estimate_complexity(body) if body else 1
        is_ctor = name == "__construct"

        return FunctionNode(
            name=name,
            type="constructor" if is_ctor else "method",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            parameters=params,
            return_type=return_type,
            complexity=complexity,
        )

    # ── Import extraction (``use`` declarations) ────────────────────

    def extract_imports(self, source_code: str, tree: ts.Tree | None = None) -> list[ImportNode]:
        if tree is None:
            return []
        imports: list[ImportNode] = []
        self._walk_imports(tree.root_node, imports)
        return imports

    def _walk_imports(self, node: ts.Node, out: list[ImportNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        if node.type == "namespace_use_declaration":
            out.extend(self._build_imports(node))
            return
        for child in node.children:
            self._walk_imports(child, out)

    def _build_imports(self, node: ts.Node) -> list[ImportNode]:
        """Each ``namespace_use_clause`` becomes one ImportNode.

        ``use App\\Foo;``                  → module=App\\Foo
        ``use App\\Foo as Bar;``           → module=App\\Foo, aliases=[Bar]
        ``use App\\Foo, App\\Bar;``        → two ImportNodes
        """
        results: list[ImportNode] = []
        for child in node.children:
            if child.type != "namespace_use_clause":
                continue
            module: str | None = None
            alias: str | None = None
            for sub in child.children:
                if sub.type == "qualified_name":
                    module = sub.text.decode("utf-8")
                elif sub.type == "name" and alias is None and module is not None:
                    alias = sub.text.decode("utf-8")
            results.append(
                ImportNode(
                    name=module or child.text.decode("utf-8"),
                    type="import",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    module=module,
                    aliases=[alias] if alias else [],
                )
            )
        return results

    # ── Helpers ─────────────────────────────────────────────────────

    def _child_text_by_field(self, node: ts.Node, field: str) -> str | None:
        child = node.child_by_field_name(field)
        if child:
            return child.text.decode("utf-8")
        return None

    def _find_body(self, node: ts.Node) -> ts.Node | None:
        """Locate the ``compound_statement`` / declaration body of a node, if present."""
        body = node.child_by_field_name("body")
        if body is not None:
            return body
        for child in node.children:
            if child.type in _BODY_TYPES or child.type == "compound_statement":
                return child
        return None

    def _extract_parameters(self, decl_node: ts.Node) -> list[ParameterNode]:
        params_node = self._find_by_type(decl_node, "formal_parameters")
        if params_node is None:
            return []
        params: list[ParameterNode] = []
        for child in params_node.children:
            if child.type in ("simple_parameter", "variadic_parameter", "optional_parameter"):
                params.append(self._build_parameter(child))
        return params

    def _build_parameter(self, param_node: ts.Node) -> ParameterNode:
        # Variable name lives in a ``variable_name`` child ($ token + name); strip the $.
        var_node = self._find_by_type(param_node, "variable_name")
        name = "?"
        if var_node is not None:
            raw = var_node.text.decode("utf-8")
            name = raw.lstrip("$")
        # Type is the first _TYPE_NODES child of the parameter.
        type_text = self._first_type_text(param_node)
        return ParameterNode(
            name=name,
            type=type_text,
            line_start=param_node.start_point[0] + 1,
        )

    def _extract_return_type(self, decl_node: ts.Node) -> str | None:
        """Return type is the first _TYPE_NODES child appearing after ``formal_parameters``."""
        passed_params = False
        for child in decl_node.children:
            if child.type == "formal_parameters":
                passed_params = True
                continue
            if passed_params and child.type in _TYPE_NODES:
                return child.text.decode("utf-8")
        return None

    def _first_type_text(self, node: ts.Node) -> str | None:
        for child in node.children:
            if child.type in _TYPE_NODES:
                return child.text.decode("utf-8")
        return None

    def _find_by_type(self, node: ts.Node, node_type: str) -> ts.Node | None:
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    def _estimate_complexity(self, node: ts.Node) -> int:
        """Rough cyclomatic complexity from PHP control-flow nodes."""
        count = 1
        stack = [node]
        complexity_types = frozenset(
            {
                "if_statement",
                "for_statement",
                "foreach_statement",
                "while_statement",
                "do_statement",
                "switch_statement",
                "catch_clause",
                "conditional_expression",
                "match_expression",
                "coalesce_expression",
            }
        )
        while stack:
            current = stack.pop()
            if current.type in complexity_types:
                count += 1
            elif current.type == "binary_expression":
                txt = current.text.decode("utf-8")
                if "&&" in txt or "||" in txt:
                    count += txt.count("&&") + txt.count("||")
            stack.extend(current.children)
        return count
