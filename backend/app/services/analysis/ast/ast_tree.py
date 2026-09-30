from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel, Field

from app.services.analysis.ast.nodes import ClassNode, FunctionNode, ImportNode, VariableNode


class ErrorNode(BaseModel):
    type: str = "error"
    line_start: int
    line_end: int
    message: str | None = None


class ASTTree(BaseModel):
    language: str
    source_path: str | None = None
    functions: list[FunctionNode] = Field(default_factory=list)
    classes: list[ClassNode] = Field(default_factory=list)
    imports: list[ImportNode] = Field(default_factory=list)
    variables: list[VariableNode] = Field(default_factory=list)
    error_nodes: list[ErrorNode] = Field(default_factory=list)
    parse_time_ms: float = 0.0
    loc_count: int = 0

    def all_functions(self, include_nested: bool = True) -> list[FunctionNode]:
        result = list(self.functions)
        if include_nested:
            for cls in self.classes:
                result.extend(cls.methods)
        return result

    def all_classes(self) -> list[ClassNode]:
        return list(self.classes)

    def all_imports(self) -> list[ImportNode]:
        return list(self.imports)

    def traverse(self) -> Iterator[FunctionNode | ClassNode | ImportNode | VariableNode]:
        yield from self.imports
        yield from self.variables
        for func in self.functions:
            yield func
            yield from func.children
        for cls in self.classes:
            yield cls
            yield from cls.methods

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, data: str) -> ASTTree:
        return cls.model_validate_json(data)

    def to_dict(self) -> dict:
        return self.model_dump()

    def has_errors(self) -> bool:
        return len(self.error_nodes) > 0
