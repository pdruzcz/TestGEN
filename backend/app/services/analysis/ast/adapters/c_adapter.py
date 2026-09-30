"""C AST parser adapter using tree-sitter.

Story 1.19 — Production C adapter extracting functions, structs,
enums, typedefs, and #include directives.
"""

from __future__ import annotations

import tree_sitter as ts
import tree_sitter_c as tsc

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
)
from app.services.analysis.ast.registry import register_parser

_C_LANG = ts.Language(tsc.language())

_SKIP_TYPES = frozenset({"string_literal", "char_literal", "line_comment", "block_comment", "number_literal"})


@register_parser("c")
class CAdapter(BaseASTParser):
    """Tree-sitter-based AST parser for C source code."""

    language = "c"
    _ts_language = _C_LANG

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
        if node.type == "function_definition":
            out.append(self._build_function_node(node))
            return
        for child in node.children:
            self._walk_functions(child, out)

    def _build_function_node(self, node: ts.Node) -> FunctionNode:
        decl = node.child_by_field_name("declarator")
        name, params = self._extract_decl_info(decl) if decl else ("<anonymous>", [])
        return_type = self._extract_return_type(node)
        body = node.child_by_field_name("body")
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

    def _extract_decl_info(self, decl: ts.Node) -> tuple[str, list[ParameterNode]]:
        """Extract function name and parameters from a declarator node."""
        name = "<anonymous>"
        params: list[ParameterNode] = []

        # Handle pointer declarators: int *foo(args)
        current = decl
        while current.type == "pointer_declarator":
            inner = current.child_by_field_name("declarator")
            if inner:
                current = inner
            else:
                break

        # Get name
        name_node = current.child_by_field_name("declarator")
        if name_node:
            name = name_node.text.decode("utf-8")
        elif current.type == "identifier":
            name = current.text.decode("utf-8")

        # Get parameters
        params_node = current.child_by_field_name("parameters")
        if params_node:
            params = self._extract_parameters(params_node)

        return name, params

    # ── Class extraction (struct/enum/typedef as "class-like") ──────

    def extract_classes(self, source_code: str, tree: ts.Tree | None = None) -> list[ClassNode]:
        if tree is None:
            return []
        classes: list[ClassNode] = []
        self._walk_classes(tree.root_node, classes)
        return classes

    def _walk_classes(self, node: ts.Node, out: list[ClassNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        if node.type in ("struct_specifier", "enum_specifier"):
            cls = self._build_struct_node(node)
            if cls:
                out.append(cls)
            return
        for child in node.children:
            self._walk_classes(child, out)

    def _build_struct_node(self, node: ts.Node) -> ClassNode | None:
        name = self._child_text_by_field(node, "name") or self._child_text_by_type(node, "type_identifier")
        if name is None:
            # Anonymous struct/enum — skip unless it has a body
            body = node.child_by_field_name("body")
            if body is None:
                return None
            name = f"<anonymous_{node.type}>"

        return ClassNode(
            name=name,
            type=node.type.replace("_specifier", ""),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            complexity=1,
        )

    # ── Import extraction (#include) ────────────────────────────────

    def extract_imports(self, source_code: str, tree: ts.Tree | None = None) -> list[ImportNode]:
        if tree is None:
            return []
        imports: list[ImportNode] = []
        self._walk_imports(tree.root_node, imports)
        return imports

    def _walk_imports(self, node: ts.Node, out: list[ImportNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        if node.type == "preproc_include":
            out.append(self._build_import(node))
            return
        for child in node.children:
            self._walk_imports(child, out)

    def _build_import(self, node: ts.Node) -> ImportNode:
        module: str | None = None
        for child in node.children:
            if child.type == "string_literal":
                module = child.text.decode("utf-8").strip("\"")
            elif child.type == "system_lib_string":
                module = child.text.decode("utf-8").strip("<>")

        return ImportNode(
            name=node.text.decode("utf-8"),
            type="import",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            module=module,
        )

    # ── Helpers ─────────────────────────────────────────────────────

    def _child_text_by_field(self, node: ts.Node, field: str) -> str | None:
        child = node.child_by_field_name(field)
        if child:
            return child.text.decode("utf-8")
        return None

    def _child_text_by_type(self, node: ts.Node, node_type: str) -> str | None:
        for child in node.children:
            if child.type == node_type:
                return child.text.decode("utf-8")
        return None

    def _extract_parameters(self, params_node: ts.Node) -> list[ParameterNode]:
        params: list[ParameterNode] = []
        for child in params_node.children:
            if child.type == "parameter_declaration":
                name_node = child.child_by_field_name("declarator")
                type_node = child.child_by_field_name("type")
                name = "<param>"
                if name_node:
                    # Unwrap pointer/array declarators
                    inner = name_node
                    while inner.type in ("pointer_declarator", "array_declarator"):
                        d = inner.child_by_field_name("declarator")
                        if d:
                            inner = d
                        else:
                            break
                    name = inner.text.decode("utf-8")
                params.append(ParameterNode(
                    name=name,
                    type=type_node.text.decode("utf-8") if type_node else None,
                    line_start=child.start_point[0] + 1,
                ))
        return params

    def _extract_return_type(self, func_node: ts.Node) -> str | None:
        type_node = func_node.child_by_field_name("type")
        if type_node:
            return type_node.text.decode("utf-8")
        return None

    def _estimate_complexity(self, node: ts.Node) -> int:
        count = 1
        stack = [node]
        complexity_types = frozenset({
            "if_statement", "for_statement", "while_statement", "do_statement",
            "switch_statement", "case_statement", "goto_statement",
            "ternary_expression", "&&", "||",
        })
        while stack:
            current = stack.pop()
            if current.type in complexity_types:
                count += 1
            stack.extend(current.children)
        return count
