from pydantic import BaseModel, Field


class ParameterNode(BaseModel):
    name: str
    type: str | None = None
    default_value: str | None = None
    line_start: int | None = None


class BaseASTNode(BaseModel):
    """Base for all AST node types — guarantees AC1 field contract."""

    name: str
    type: str
    line_start: int
    line_end: int
    docstring: str | None = None
    parameters: list[ParameterNode] = Field(default_factory=list)
    return_type: str | None = None
    complexity: int = 0


class FunctionNode(BaseASTNode):
    type: str = "function"
    complexity: int = 1
    children: list["FunctionNode"] = Field(default_factory=list)


class ClassNode(BaseASTNode):
    type: str = "class"
    complexity: int = 1
    methods: list[FunctionNode] = Field(default_factory=list)
    bases: list[str] = Field(default_factory=list)


class ImportNode(BaseASTNode):
    type: str = "import"
    module: str | None = None
    aliases: list[str] = Field(default_factory=list)


class VariableNode(BaseASTNode):
    type: str = "variable"
    inferred_type: str | None = None
