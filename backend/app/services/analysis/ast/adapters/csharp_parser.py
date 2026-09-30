"""C# / .NET AST parser adapter using tree-sitter.

Story 1.18 — Production C# adapter extracting methods, classes,
interfaces, structs, enums, using directives, and properties.
"""

from __future__ import annotations

import tree_sitter as ts
import tree_sitter_c_sharp as tscs

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
)
from app.services.analysis.ast.registry import register_parser

_CS_LANG = ts.Language(tscs.language())

_SKIP_TYPES = frozenset({"string_literal", "character_literal", "line_comment", "block_comment", "interpolated_string_text"})
_CLASS_TYPES = frozenset({
    "class_declaration", "interface_declaration", "struct_declaration",
    "enum_declaration", "record_declaration",
})


@register_parser("csharp")
@register_parser("c#")
class CSharpAdapter(BaseASTParser):
    """Tree-sitter-based AST parser for C# source code."""

    language = "csharp"
    _ts_language = _CS_LANG

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
        if node.type in _CLASS_TYPES:
            return  # methods are class members
        if node.type == "method_declaration":
            out.append(self._build_method_node(node))
            return
        if node.type == "local_function_statement":
            out.append(self._build_method_node(node))
            return
        for child in node.children:
            self._walk_functions(child, out)

    def _build_method_node(self, node: ts.Node) -> FunctionNode:
        name = self._child_text_by_field(node, "name") or "<anonymous>"
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        body = node.child_by_field_name("body")
        complexity = self._estimate_complexity(body) if body else 1

        return FunctionNode(
            name=name,
            type="method",
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
        if node.type in ("class_declaration", "interface_declaration", "struct_declaration",
                          "enum_declaration", "record_declaration"):
            out.append(self._build_class_node(node))
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    self._walk_classes(child, out)
            return
        for child in node.children:
            self._walk_classes(child, out)

    def _build_class_node(self, node: ts.Node) -> ClassNode:
        name = self._child_text_by_field(node, "name") or "Unknown"
        bases = self._extract_bases(node)
        methods = self._extract_class_methods(node)
        complexity = sum(m.complexity for m in methods) if methods else 1

        return ClassNode(
            name=name,
            type=node.type.replace("_declaration", ""),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            complexity=complexity,
            methods=methods,
            bases=bases,
        )

    def _extract_bases(self, node: ts.Node) -> list[str]:
        bases: list[str] = []
        # base_list is a named child but NOT a named field in some grammar versions
        for child in node.children:
            if child.type == "base_list":
                for sub in child.children:
                    if sub.is_named:
                        bases.append(sub.text.decode("utf-8"))
                break
        return bases

    def _extract_class_methods(self, class_node: ts.Node) -> list[FunctionNode]:
        methods: list[FunctionNode] = []
        body = class_node.child_by_field_name("body")
        if body is None:
            return methods
        for child in body.children:
            if child.type == "method_declaration":
                methods.append(self._build_method_node(child))
            elif child.type == "constructor_declaration":
                methods.append(self._build_constructor_node(child))
            elif child.type == "property_declaration":
                methods.append(self._build_property_node(child))
        return methods

    def _build_constructor_node(self, node: ts.Node) -> FunctionNode:
        name = self._child_text_by_field(node, "name") or "<init>"
        params = self._extract_parameters(node)
        body = node.child_by_field_name("body")
        complexity = self._estimate_complexity(body) if body else 1

        return FunctionNode(
            name=name,
            type="constructor",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            parameters=params,
            return_type=None,
            complexity=complexity,
        )

    def _build_property_node(self, node: ts.Node) -> FunctionNode:
        name = self._child_text_by_field(node, "name") or "<property>"
        type_node = node.child_by_field_name("type")
        return_type = type_node.text.decode("utf-8") if type_node else None

        return FunctionNode(
            name=name,
            type="property",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            return_type=return_type,
            complexity=1,
        )

    # ── Import extraction ───────────────────────────────────────────

    def extract_imports(self, source_code: str, tree: ts.Tree | None = None) -> list[ImportNode]:
        if tree is None:
            return []
        imports: list[ImportNode] = []
        self._walk_imports(tree.root_node, imports)
        return imports

    def _walk_imports(self, node: ts.Node, out: list[ImportNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        if node.type == "using_directive":
            out.append(self._build_import(node))
            return
        for child in node.children:
            self._walk_imports(child, out)

    def _build_import(self, node: ts.Node) -> ImportNode:
        module: str | None = None
        aliases: list[str] = []
        for child in node.children:
            if child.type in ("identifier", "qualified_name", "name"):
                if module is None:
                    module = child.text.decode("utf-8")
                else:
                    aliases.append(child.text.decode("utf-8"))

        return ImportNode(
            name=node.text.decode("utf-8"),
            type="import",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            module=module,
            aliases=aliases,
        )

    # ── Helpers ─────────────────────────────────────────────────────

    def _child_text_by_field(self, node: ts.Node, field: str) -> str | None:
        child = node.child_by_field_name(field)
        if child:
            return child.text.decode("utf-8")
        return None

    def _extract_parameters(self, method_node: ts.Node) -> list[ParameterNode]:
        params_node = method_node.child_by_field_name("parameters")
        if params_node is None:
            return []
        params: list[ParameterNode] = []
        for child in params_node.children:
            if child.type == "parameter":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                params.append(ParameterNode(
                    name=name_node.text.decode("utf-8") if name_node else "?",
                    type=type_node.text.decode("utf-8") if type_node else None,
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "variadic_parameter":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                params.append(ParameterNode(
                    name=f"params {name_node.text.decode('utf-8')}" if name_node else "params ...",
                    type=type_node.text.decode("utf-8") if type_node else None,
                    line_start=child.start_point[0] + 1,
                ))
        return params

    def _extract_return_type(self, method_node: ts.Node) -> str | None:
        # tree-sitter C# uses "returns" for method return type
        type_node = method_node.child_by_field_name("returns")
        if type_node:
            return type_node.text.decode("utf-8")
        type_node = method_node.child_by_field_name("type")
        if type_node:
            return type_node.text.decode("utf-8")
        return None

    def _estimate_complexity(self, node: ts.Node) -> int:
        count = 1
        stack = [node]
        complexity_types = frozenset({
            "if_statement", "for_statement", "foreach_statement", "while_statement",
            "do_statement", "switch_statement", "switch_expression_arm",
            "catch_clause", "ternary_expression", "and_expression", "or_expression",
        })
        while stack:
            current = stack.pop()
            if current.type in complexity_types:
                count += 1
            stack.extend(current.children)
        return count
