from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import tree_sitter as ts

from app.services.analysis.ast.ast_tree import ASTTree, ErrorNode

if TYPE_CHECKING:
    from app.services.analysis.ast.nodes import ClassNode, FunctionNode, ImportNode

logger = logging.getLogger(__name__)


class BaseASTParser(ABC):
    language: str
    _ts_language: ts.Language

    def __init__(self) -> None:
        self._parser: ts.Parser | None = None

    def _get_parser(self) -> ts.Parser:
        if self._parser is None:
            self._parser = ts.Parser(self._ts_language)
        return self._parser

    def parse(self, source_code: str, source_path: str | None = None) -> ASTTree:
        start_time = time.time()
        parser = self._get_parser()
        tree = parser.parse(source_code.encode("utf-8"))

        loc_count = source_code.count("\n") + 1 if source_code else 1
        # Trailing newline doesn't add an extra line
        if source_code and source_code.endswith("\n") and loc_count > 1:
            loc_count -= 1
        error_nodes = self._collect_error_nodes(tree.root_node)

        functions = self.extract_functions(source_code, tree)
        classes = self.extract_classes(source_code, tree)
        imports = self.extract_imports(source_code, tree)

        parse_time_ms = (time.time() - start_time) * 1000

        return ASTTree(
            language=self.language,
            source_path=source_path,
            functions=functions,
            classes=classes,
            imports=imports,
            error_nodes=error_nodes,
            parse_time_ms=parse_time_ms,
            loc_count=loc_count,
        )

    @abstractmethod
    def extract_functions(self, source_code: str, tree: ts.Tree | None = None) -> list[FunctionNode]:
        pass

    @abstractmethod
    def extract_classes(self, source_code: str, tree: ts.Tree | None = None) -> list[ClassNode]:
        pass

    @abstractmethod
    def extract_imports(self, source_code: str, tree: ts.Tree | None = None) -> list[ImportNode]:
        pass

    def _collect_error_nodes(self, node: ts.Node) -> list[ErrorNode]:
        errors: list[ErrorNode] = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current.is_error or current.type == "ERROR":
                errors.append(
                    ErrorNode(
                        line_start=current.start_point[0] + 1,
                        line_end=current.end_point[0] + 1,
                        message=f"Syntax error at line {current.start_point[0] + 1}",
                    )
                )
            elif current.is_missing:
                errors.append(
                    ErrorNode(
                        line_start=current.start_point[0] + 1,
                        line_end=current.end_point[0] + 1,
                        message=f"Missing node at line {current.start_point[0] + 1}",
                    )
                )
            stack.extend(current.children)
        return errors
