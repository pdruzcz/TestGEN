"""Java AST parser adapter using tree-sitter.

Story 1.16 — Production Java adapter extracting methods, classes,
interfaces, enums, imports, parameters, and return types.
"""

from __future__ import annotations

import tree_sitter as ts
import tree_sitter_java as tsjava

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
)
from app.services.analysis.ast.registry import register_parser

_JAVA_LANG = ts.Language(tsjava.language())

_SKIP_TYPES = frozenset({"string_literal", "character_literal", "line_comment", "block_comment"})
_CLASS_TYPES = frozenset({"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"})


@register_parser("java")
class JavaAdapter(BaseASTParser):
    """Tree-sitter-based AST parser for Java source code."""

    language = "java"
    _ts_language = _JAVA_LANG

    # ── Function (method) extraction ────────────────────────────────

    def extract_functions(self, source_code: str, tree: ts.Tree | None = None) -> list[FunctionNode]:
        if tree is None:
            return []
        functions: list[FunctionNode] = []
        self._walk_functions(tree.root_node, functions)
        return functions

    def _walk_functions(self, node: ts.Node, out: list[FunctionNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        # Skip methods inside class/interface/enum bodies — they become class methods
        if node.type in _CLASS_TYPES:
            return
        if node.type == "method_declaration":
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
        if node.type in _CLASS_TYPES:
            out.append(self._build_class_node(node))
            # Recurse into body for nested classes
            body = node.child_by_field_name("body")
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
            type=node.type.replace("_declaration", ""),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            complexity=complexity,
            methods=methods,
            bases=bases,
        )

    def _extract_super_types(self, node: ts.Node) -> list[str]:
        bases: list[str] = []
        # Field names differ: class uses "superclass"/"interfaces",
        # interface uses unnamed fields. Search by node type instead.
        for child in node.children:
            if child.type == "superclass":
                # extends one class
                for sub in child.children:
                    if sub.is_named:
                        bases.append(sub.text.decode("utf-8"))
            elif child.type in ("super_interfaces", "extends_interfaces"):
                # implements/extends — contains type_list with type_identifiers
                for sub in child.children:
                    if sub.is_named:
                        if sub.type == "type_list":
                            for inner in sub.children:
                                if inner.is_named:
                                    bases.append(inner.text.decode("utf-8"))
                        else:
                            bases.append(sub.text.decode("utf-8"))
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
        if node.type == "import_declaration":
            out.append(self._build_import(node))
            return
        for child in node.children:
            self._walk_imports(child, out)

    def _build_import(self, node: ts.Node) -> ImportNode:
        module: str | None = None
        is_wildcard = False
        for child in node.children:
            if child.type == "scoped_identifier":
                module = child.text.decode("utf-8")
            elif child.type in ("asterisk",) or (child.is_named and child.text.decode("utf-8") == "*"):
                is_wildcard = True
        # For wildcard imports, append * to module for consistency
        if is_wildcard and module:
            module = f"{module}.*"

        return ImportNode(
            name=module or node.text.decode("utf-8"),
            type="import",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            module=module,
            aliases=["*"] if is_wildcard else [],
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
            if child.type == "formal_parameter":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                params.append(ParameterNode(
                    name=name_node.text.decode("utf-8") if name_node else "?",
                    type=type_node.text.decode("utf-8") if type_node else None,
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "spread_parameter":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                params.append(ParameterNode(
                    name=f"...{name_node.text.decode('utf-8')}" if name_node else "...?",
                    type=type_node.text.decode("utf-8") if type_node else None,
                    line_start=child.start_point[0] + 1,
                ))
        return params

    def _extract_return_type(self, method_node: ts.Node) -> str | None:
        type_node = method_node.child_by_field_name("type")
        if type_node:
            return type_node.text.decode("utf-8")
        return None

    def _estimate_complexity(self, node: ts.Node) -> int:
        count = 1
        stack = [node]
        complexity_types = frozenset({
            "if_statement", "for_statement", "while_statement", "do_statement",
            "switch_block_statement_group", "catch_clause", "ternary_expression",
            "&&", "||",
        })
        while stack:
            current = stack.pop()
            if current.type in complexity_types:
                count += 1
            stack.extend(current.children)
        return count
