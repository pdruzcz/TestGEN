"""TypeScript AST parser adapter using tree-sitter.

Story 1.17 — Production TypeScript adapter extending JS patterns
with type annotations, interfaces, and type aliases.
"""

from __future__ import annotations

import tree_sitter as ts
import tree_sitter_typescript as tstypescript

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
)
from app.services.analysis.ast.registry import register_parser

_TS_LANG = ts.Language(tstypescript.language_typescript())

_SKIP_TYPES = frozenset({"string", "template_string", "comment", "regex", "number"})
_FUNCTION_TYPES = frozenset({
    "function_declaration", "function_signature", "generator_function_declaration",
    "arrow_function",
})


@register_parser("typescript")
class TypeScriptAdapter(BaseASTParser):
    """Tree-sitter-based AST parser for TypeScript source code."""

    language = "typescript"
    _ts_language = _TS_LANG

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
        if node.type in ("class_declaration", "interface_declaration", "type_alias_declaration"):
            return
        if node.type in _FUNCTION_TYPES:
            fn = self._build_function_node(node)
            out.append(fn)
            return
        for child in node.children:
            self._walk_functions(child, out)

    def _build_function_node(self, node: ts.Node) -> FunctionNode:
        name = self._extract_function_name(node)
        params = self._extract_parameters(node)
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

    def _extract_function_name(self, node: ts.Node) -> str:
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode("utf-8")
        parent = node.parent
        if parent and parent.type in ("variable_declarator", "assignment_expression"):
            left = parent.child_by_field_name("name") or parent.child_by_field_name("left")
            if left:
                return left.text.decode("utf-8")
        return "<anonymous>"

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
        if node.type in ("class_declaration", "interface_declaration"):
            out.append(self._build_class_node(node))
            return
        for child in node.children:
            self._walk_classes(child, out)

    def _build_class_node(self, node: ts.Node) -> ClassNode:
        name = self._child_text_by_field(node, "name") or "Unknown"
        bases = self._extract_heritage(node)
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

    def _extract_heritage(self, node: ts.Node) -> list[str]:
        bases: list[str] = []
        # class_heritage is an unnamed field — find by type
        for child in node.children:
            if child.type == "class_heritage":
                for sub in child.children:
                    if sub.is_named:
                        # extends_clause / implements_clause contain type identifiers
                        if sub.type in ("extends_clause", "implements_clause"):
                            for inner in sub.children:
                                if inner.is_named:
                                    bases.append(inner.text.decode("utf-8"))
                        else:
                            bases.append(sub.text.decode("utf-8"))
                break
        return bases

    def _extract_class_methods(self, class_node: ts.Node) -> list[FunctionNode]:
        methods: list[FunctionNode] = []
        body = class_node.child_by_field_name("body")
        if body is None:
            return methods
        for child in body.children:
            if child.type in ("method_definition", "public_field_definition",
                              "abstract_method_signature", "method_signature",
                              "getter_property", "setter_property"):
                name = self._child_text_by_field(child, "name") or "<method>"
                params = self._extract_parameters(child)
                return_type = self._extract_return_type(child)
                method_body = child.child_by_field_name("body")
                complexity = self._estimate_complexity(method_body) if method_body else 1
                methods.append(FunctionNode(
                    name=name,
                    type="method",
                    line_start=child.start_point[0] + 1,
                    line_end=child.end_point[0] + 1,
                    parameters=params,
                    return_type=return_type,
                    complexity=complexity,
                ))
        return methods

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
        if node.type == "import_statement":
            out.append(self._build_import(node))
            return
        for child in node.children:
            self._walk_imports(child, out)

    def _build_import(self, node: ts.Node) -> ImportNode:
        module: str | None = None
        aliases: list[str] = []
        for child in node.children:
            if child.type == "string":
                module = child.text.decode("utf-8").strip("\"'")
            elif child.type == "import_clause":
                for clause_child in child.children:
                    if clause_child.type == "identifier":
                        aliases.append(clause_child.text.decode("utf-8"))
                    elif clause_child.type == "named_imports":
                        for spec in clause_child.children:
                            if spec.type == "import_specifier":
                                alias_node = spec.child_by_field_name("alias")
                                name_node = spec.child_by_field_name("name")
                                if alias_node:
                                    aliases.append(alias_node.text.decode("utf-8"))
                                elif name_node:
                                    aliases.append(name_node.text.decode("utf-8"))
                    elif clause_child.type == "namespace_import":
                        for ns_child in clause_child.children:
                            if ns_child.type == "identifier":
                                aliases.append(f"* as {ns_child.text.decode('utf-8')}")

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

    def _extract_parameters(self, func_node: ts.Node) -> list[ParameterNode]:
        params_node = func_node.child_by_field_name("parameters")
        if params_node is None:
            return []
        params: list[ParameterNode] = []
        for child in params_node.children:
            if child.type == "required_parameter":
                name_node = child.child_by_field_name("pattern")
                type_node = child.child_by_field_name("type")
                name = name_node.text.decode("utf-8") if name_node else "?"
                # type is type_annotation ": number" — extract inner type
                param_type = None
                if type_node:
                    for sub in type_node.children:
                        if sub.is_named:
                            param_type = sub.text.decode("utf-8")
                            break
                    if not param_type:
                        param_type = type_node.text.decode("utf-8").lstrip(":").strip()
                params.append(ParameterNode(
                    name=name,
                    type=param_type,
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "optional_parameter":
                name_node = child.child_by_field_name("pattern")
                type_node = child.child_by_field_name("type")
                name = name_node.text.decode("utf-8") if name_node else "?"
                param_type = None
                if type_node:
                    for sub in type_node.children:
                        if sub.is_named:
                            param_type = sub.text.decode("utf-8")
                            break
                    if not param_type:
                        param_type = type_node.text.decode("utf-8").lstrip(":").strip()
                params.append(ParameterNode(
                    name=name,
                    type=param_type,
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "rest_parameter":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                name = f"...{name_node.text.decode('utf-8')}" if name_node else "...?"
                params.append(ParameterNode(
                    name=name,
                    type=type_node.text.decode("utf-8") if type_node else None,
                    line_start=child.start_point[0] + 1,
                ))
        return params

    def _extract_return_type(self, func_node: ts.Node) -> str | None:
        type_node = func_node.child_by_field_name("return_type")
        if type_node:
            text = type_node.text.decode("utf-8")
            # type_annotation includes ": prefix" — get the type child
            for child in type_node.children:
                if child.is_named:
                    return child.text.decode("utf-8")
            # Fallback: strip colon
            return text.lstrip(":").strip()
        return None

    def _estimate_complexity(self, node: ts.Node) -> int:
        count = 1
        stack = [node]
        complexity_types = frozenset({
            "if_statement", "for_statement", "for_in_statement", "while_statement",
            "do_statement", "switch_case", "catch_clause", "ternary_expression",
            "&&", "||", "??",
        })
        while stack:
            current = stack.pop()
            if current.type in complexity_types:
                count += 1
            stack.extend(current.children)
        return count
