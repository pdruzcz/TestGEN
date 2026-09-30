"""C++ AST parser adapter using tree-sitter.

Story 1.19 — Production C++ adapter extracting functions, classes,
structs, namespaces, templates, and #include directives.
"""

from __future__ import annotations

import tree_sitter as ts
import tree_sitter_cpp as tscpp

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
)
from app.services.analysis.ast.registry import register_parser

_CPP_LANG = ts.Language(tscpp.language())

_SKIP_TYPES = frozenset({
    "string_literal", "char_literal", "line_comment", "block_comment",
    "number_literal", "raw_string_literal",
})
_CLASS_TYPES = frozenset({
    "class_specifier", "struct_specifier", "enum_specifier",
})


@register_parser("cpp")
@register_parser("c++")
class CppAdapter(BaseASTParser):
    """Tree-sitter-based AST parser for C++ source code."""

    language = "cpp"
    _ts_language = _CPP_LANG

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
        if node.type == "function_definition":
            out.append(self._build_function_node(node))
            return
        if node.type == "declaration" and self._is_function_declaration(node):
            out.append(self._build_function_node(node))
            return
        for child in node.children:
            self._walk_functions(child, out)

    def _is_function_declaration(self, node: ts.Node) -> bool:
        """Check if a declaration node is a function declaration."""
        decl = node.child_by_field_name("declarator")
        if decl is None:
            return False
        current = decl
        while current.type in ("pointer_declarator", "reference_declarator"):
            inner = current.child_by_field_name("declarator")
            if inner:
                current = inner
            else:
                break
        return current.child_by_field_name("parameters") is not None

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
        name = "<anonymous>"
        params: list[ParameterNode] = []

        current = decl
        # Unwrap pointer/reference layers to find the core declarator
        while current.type in ("pointer_declarator", "reference_declarator"):
            inner = current.child_by_field_name("declarator")
            if inner:
                current = inner
            else:
                break

        # function_declarator: name + parameter_list
        if current.type == "function_declarator":
            name_decl = current.child_by_field_name("declarator")
            if name_decl:
                name = self._unwrap_declarator_name(name_decl)
            elif current.child_by_field_name("name"):
                name = current.child_by_field_name("name").text.decode("utf-8")
            else:
                # First identifier child
                for child in current.children:
                    if child.type in ("identifier", "type_identifier"):
                        name = child.text.decode("utf-8")
                        break
            params_node = current.child_by_field_name("parameters")
            if params_node:
                params = self._extract_parameters(params_node)
            return name, params

        # qualified_identifier: Namespace::func
        if current.type == "qualified_identifier":
            for child in current.children:
                if child.type == "identifier":
                    name = child.text.decode("utf-8")
            params_node = current.child_by_field_name("parameters")
            if params_node:
                params = self._extract_parameters(params_node)
            return name, params

        # Simple declarator
        name_node = current.child_by_field_name("declarator")
        if name_node:
            name = name_node.text.decode("utf-8")
        elif current.type == "identifier":
            name = current.text.decode("utf-8")

        params_node = current.child_by_field_name("parameters")
        if params_node:
            params = self._extract_parameters(params_node)

        return name, params

    def _unwrap_declarator_name(self, node: ts.Node) -> str:
        """Recursively unwrap declarator to get the base name."""
        if node.type in ("pointer_declarator", "reference_declarator"):
            inner = node.child_by_field_name("declarator")
            if inner:
                return self._unwrap_declarator_name(inner)
        if node.type in ("identifier", "type_identifier"):
            return node.text.decode("utf-8")
        return node.text.decode("utf-8")

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
        if node.type in ("class_specifier", "struct_specifier"):
            cls = self._build_class_node(node)
            if cls:
                out.append(cls)
            # Recurse into body for nested classes
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    self._walk_classes(child, out)
            return
        if node.type == "enum_specifier":
            cls = self._build_enum_node(node)
            if cls:
                out.append(cls)
            return
        for child in node.children:
            self._walk_classes(child, out)

    def _build_class_node(self, node: ts.Node) -> ClassNode | None:
        name = self._child_text_by_field(node, "name")
        if name is None:
            name = self._child_text_by_type(node, "type_identifier")
        if name is None:
            return None

        bases = self._extract_bases(node)
        methods = self._extract_class_methods(node)
        complexity = sum(m.complexity for m in methods) if methods else 1

        return ClassNode(
            name=name,
            type=node.type.replace("_specifier", ""),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            complexity=complexity,
            methods=methods,
            bases=bases,
        )

    def _build_enum_node(self, node: ts.Node) -> ClassNode | None:
        name = self._child_text_by_field(node, "name")
        if name is None:
            name = self._child_text_by_type(node, "type_identifier")
        if name is None:
            return None

        return ClassNode(
            name=name,
            type="enum",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            complexity=1,
        )

    def _extract_bases(self, node: ts.Node) -> list[str]:
        bases: list[str] = []
        # C++ class Foo : public Bar, private Baz
        for child in node.children:
            if child.type == "base_class_clause":
                for base_child in child.children:
                    if base_child.is_named and base_child.type not in ("public", "private", "protected"):
                        bases.append(base_child.text.decode("utf-8"))
        return bases

    def _extract_class_methods(self, class_node: ts.Node) -> list[FunctionNode]:
        methods: list[FunctionNode] = []
        body = class_node.child_by_field_name("body")
        if body is None:
            return methods
        for child in body.children:
            if child.type == "function_definition":
                methods.append(self._build_method_node(child))
            elif child.type == "declaration" and self._is_function_declaration(child):
                methods.append(self._build_method_node(child))
            elif child.type == "constructor_definition":
                methods.append(self._build_constructor_node(child))
            elif child.type == "destructor_definition":
                methods.append(self._build_destructor_node(child))
        return methods

    def _build_method_node(self, node: ts.Node) -> FunctionNode:
        decl = node.child_by_field_name("declarator")
        name, params = self._extract_decl_info(decl) if decl else ("<method>", [])
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

    def _build_constructor_node(self, node: ts.Node) -> FunctionNode:
        decl = node.child_by_field_name("declarator")
        name = "<init>"
        params: list[ParameterNode] = []
        if decl:
            name = decl.text.decode("utf-8").split("(")[0].strip()
            params_node = decl.child_by_field_name("parameters")
            if params_node:
                params = self._extract_parameters(params_node)

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

    def _build_destructor_node(self, node: ts.Node) -> FunctionNode:
        decl = node.child_by_field_name("declarator")
        name = "<destructor>"
        if decl:
            name = decl.text.decode("utf-8").split("(")[0].strip()

        body = node.child_by_field_name("body")
        complexity = self._estimate_complexity(body) if body else 1

        return FunctionNode(
            name=name,
            type="destructor",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            return_type=None,
            complexity=complexity,
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
                    inner = name_node
                    while inner.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
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
            elif child.type == "optional_parameter_declaration":
                name_node = child.child_by_field_name("declarator")
                type_node = child.child_by_field_name("type")
                name = "<param>"
                if name_node:
                    inner = name_node
                    while inner.type in ("pointer_declarator", "reference_declarator"):
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
            elif child.type == "variadic_parameter":
                params.append(ParameterNode(
                    name="...",
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
            "if_statement", "for_statement", "for_range_loop", "while_statement",
            "do_statement", "switch_statement", "case_statement",
            "catch_clause", "goto_statement", "ternary_expression",
            "&&", "||", "co_await_expression",
        })
        while stack:
            current = stack.pop()
            if current.type in complexity_types:
                count += 1
            stack.extend(current.children)
        return count
