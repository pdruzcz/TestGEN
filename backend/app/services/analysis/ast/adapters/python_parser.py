"""Python AST parser adapter using tree-sitter.

Story 1.15 — Production Python adapter with full extraction of functions,
classes, imports, methods, parameters, return types, and docstrings.
"""

from __future__ import annotations

import tree_sitter as ts
import tree_sitter_python as tspython

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
)
from app.services.analysis.ast.registry import register_parser

_PYTHON_LANG = ts.Language(tspython.language())

# Node types to skip during traversal (avoid false positives)
_SKIP_TYPES = frozenset({"string", "comment", "block_comment", "string_content"})


@register_parser("python")
class PythonAdapter(BaseASTParser):
    """Tree-sitter-based AST parser for Python source code."""

    language = "python"
    _ts_language = _PYTHON_LANG

    # ── Function extraction ─────────────────────────────────────────

    def extract_functions(self, source_code: str, tree: ts.Tree | None = None) -> list[FunctionNode]:
        if tree is None:
            return []
        functions: list[FunctionNode] = []
        self._walk_functions(tree.root_node, source_code, functions)
        return functions

    def _walk_functions(self, node: ts.Node, source: str, out: list[FunctionNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        # Skip function definitions inside class bodies — they become class methods
        if node.type == "class_definition":
            return
        if node.type == "function_definition":
            fn = self._build_function_node(node, source)
            out.append(fn)
            # Don't recurse into function body to avoid double-counting nested functions
            # (nested functions are collected as fn.children in _build_function_node)
            return
        for child in node.children:
            self._walk_functions(child, source, out)

    def _build_function_node(self, node: ts.Node, source: str) -> FunctionNode:
        name = self._child_text(node, "identifier") or "<anonymous>"
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        docstring = self._extract_docstring(node)
        body = node.child_by_field_name("body")
        complexity = self._estimate_complexity(body) if body else 1

        # Nested functions (collected only from direct body, not deeper walks)
        children: list[FunctionNode] = []
        if body:
            for child in body.children:
                if child.type == "function_definition":
                    children.append(self._build_function_node(child, source))

        return FunctionNode(
            name=name,
            type="function",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            docstring=docstring,
            parameters=params,
            return_type=return_type,
            complexity=complexity,
            children=children,
        )

    # ── Class extraction ────────────────────────────────────────────

    def extract_classes(self, source_code: str, tree: ts.Tree | None = None) -> list[ClassNode]:
        if tree is None:
            return []
        classes: list[ClassNode] = []
        self._walk_classes(tree.root_node, source_code, classes)
        return classes

    def _walk_classes(self, node: ts.Node, source: str, out: list[ClassNode]) -> None:
        if node.type in _SKIP_TYPES:
            return
        if node.type == "class_definition":
            out.append(self._build_class_node(node, source))
            # Also recurse into class body for nested classes
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    self._walk_classes(child, source, out)
            return
        for child in node.children:
            self._walk_classes(child, source, out)

    def _build_class_node(self, node: ts.Node, source: str) -> ClassNode:
        name = self._child_text(node, "identifier") or "Unknown"
        bases = self._extract_bases(node)
        docstring = self._extract_docstring(node)
        methods = self._extract_class_methods(node, source)
        complexity = sum(m.complexity for m in methods) if methods else 1

        return ClassNode(
            name=name,
            type="class",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            docstring=docstring,
            complexity=complexity,
            methods=methods,
            bases=bases,
        )

    def _extract_bases(self, node: ts.Node) -> list[str]:
        arg_list = node.child_by_field_name("superclasses")
        if arg_list is None:
            return []
        bases: list[str] = []
        for child in arg_list.children:
            if child.is_named:
                bases.append(child.text.decode("utf-8"))
        return bases

    def _extract_class_methods(self, class_node: ts.Node, source: str) -> list[FunctionNode]:
        methods: list[FunctionNode] = []
        body = class_node.child_by_field_name("body")
        if body is None:
            return methods
        for child in body.children:
            if child.type == "function_definition":
                methods.append(self._build_function_node(child, source))
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
            out.extend(self._build_imports(node))
        elif node.type == "import_from_statement":
            out.append(self._build_from_import(node))
            return  # don't recurse into import nodes
        else:
            for child in node.children:
                self._walk_imports(child, out)

    def _build_imports(self, node: ts.Node) -> list[ImportNode]:
        """Handle `import os` and `import os, sys` (one ImportNode per module)."""
        results: list[ImportNode] = []
        for child in node.children:
            if child.type == "dotted_name":
                results.append(ImportNode(
                    name=child.text.decode("utf-8"),
                    type="import",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    module=child.text.decode("utf-8"),
                ))
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                module = name_node.text.decode("utf-8") if name_node else None
                alias = alias_node.text.decode("utf-8") if alias_node else None
                results.append(ImportNode(
                    name=child.text.decode("utf-8"),
                    type="import",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    module=module,
                    aliases=[alias] if alias else [],
                ))
        return results

    def _build_from_import(self, node: ts.Node) -> ImportNode:
        module_name: str | None = None
        names: list[str] = []
        aliases: list[str] = []

        # First child after 'from' keyword is the module
        children = node.children
        for i, child in enumerate(children):
            if child.type == "dotted_name" and module_name is None:
                module_name = child.text.decode("utf-8")
            elif child.type in ("identifier",) and module_name is None and child.text.decode("utf-8") != "from":
                module_name = child.text.decode("utf-8")
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    names.append(name_node.text.decode("utf-8"))
                if alias_node:
                    aliases.append(alias_node.text.decode("utf-8"))
            elif child.type == "wildcard_import":
                names.append("*")
            elif child.type == "identifier" and module_name is not None:
                # Plain imported name (from os.path import join)
                names.append(child.text.decode("utf-8"))
            elif child.type == "dotted_name" and module_name is not None:
                # from foo import bar.baz
                names.append(child.text.decode("utf-8"))

        return ImportNode(
            name=node.text.decode("utf-8"),
            type="import",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            module=module_name,
            aliases=aliases if aliases else names,
        )

    # ── Helpers ─────────────────────────────────────────────────────

    def _child_text(self, node: ts.Node, child_type: str) -> str | None:
        for child in node.children:
            if child.type == child_type:
                return child.text.decode("utf-8")
        return None

    def _extract_parameters(self, func_node: ts.Node) -> list[ParameterNode]:
        params_node = func_node.child_by_field_name("parameters")
        if params_node is None:
            return []
        params: list[ParameterNode] = []
        for child in params_node.children:
            if child.type == "identifier":
                params.append(ParameterNode(
                    name=child.text.decode("utf-8"),
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "typed_parameter":
                # typed_parameter has no "name" field; first identifier child is the name
                name_text = None
                type_node = child.child_by_field_name("type")
                for sub in child.children:
                    if sub.type == "identifier":
                        name_text = sub.text.decode("utf-8")
                        break
                params.append(ParameterNode(
                    name=name_text or "?",
                    type=type_node.text.decode("utf-8") if type_node else None,
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "default_parameter":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                params.append(ParameterNode(
                    name=name_node.text.decode("utf-8") if name_node else "?",
                    default_value=value_node.text.decode("utf-8") if value_node else None,
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "typed_default_parameter":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                value_node = child.child_by_field_name("value")
                params.append(ParameterNode(
                    name=name_node.text.decode("utf-8") if name_node else "?",
                    type=type_node.text.decode("utf-8") if type_node else None,
                    default_value=value_node.text.decode("utf-8") if value_node else None,
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "list_splat_pattern":
                # text already contains the * prefix (*args)
                params.append(ParameterNode(
                    name=child.text.decode("utf-8"),
                    line_start=child.start_point[0] + 1,
                ))
            elif child.type == "dictionary_splat_pattern":
                # text already contains the ** prefix (**kwargs)
                params.append(ParameterNode(
                    name=child.text.decode("utf-8"),
                    line_start=child.start_point[0] + 1,
                ))
        return params

    def _extract_return_type(self, func_node: ts.Node) -> str | None:
        type_node = func_node.child_by_field_name("return_type")
        if type_node:
            text = type_node.text.decode("utf-8")
            # Strip leading "-> " prefix from tree-sitter output
            return text.lstrip("-> ").strip()
        return None

    def _extract_docstring(self, node: ts.Node) -> str | None:
        body = node.child_by_field_name("body")
        if body is None:
            return None
        first = body.children[0] if body.children else None
        if first and first.type == "expression_statement":
            inner = first.children[0] if first.children else None
            if inner and inner.type == "string":
                text = inner.text.decode("utf-8")
                return self._strip_docstring(text)
        return None

    @staticmethod
    def _strip_docstring(raw: str) -> str:
        """Strip Python string quotes/prefixes from a docstring."""
        # Remove raw/byte prefixes
        s = raw
        for prefix in ("r", "u", "b", "f", "rb", "br", "rf", "fr"):
            if s.lower().startswith(prefix) and len(s) > len(prefix) and s[len(prefix)] in "\"'":
                s = s[len(prefix):]
                break
        # Strip triple quotes then single quotes
        for q in ('"""', "'''"):
            if s.startswith(q) and s.endswith(q):
                s = s[3:-3]
                return s.strip()
        for q in ('"', "'"):
            if s.startswith(q) and s.endswith(q):
                s = s[1:-1]
                return s.strip()
        return s.strip()

    def _estimate_complexity(self, node: ts.Node) -> int:
        """Rough cyclomatic complexity from control flow nodes."""
        count = 1
        stack = [node]
        complexity_types = frozenset({
            "if_statement", "elif_clause", "for_statement", "while_statement",
            "except_clause", "with_statement", "conditional_expression",
            "match_statement", "case_clause",
        })
        while stack:
            current = stack.pop()
            if current.type in complexity_types:
                count += 1
            elif current.type in ("boolean_operator",):
                op = current.text.decode("utf-8") if current.children else ""
                if op in ("and", "or"):
                    count += 1
                else:
                    # Children contain the operator token
                    for ch in current.children:
                        txt = ch.text.decode("utf-8")
                        if txt in ("and", "or"):
                            count += 1
            stack.extend(current.children)
        return count
