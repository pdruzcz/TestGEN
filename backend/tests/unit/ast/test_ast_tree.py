import pytest

from app.services.analysis.ast.ast_tree import ASTTree, ErrorNode
from app.services.analysis.ast.nodes import (
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
    VariableNode,
)


@pytest.fixture
def sample_tree() -> ASTTree:
    return ASTTree(
        language="python",
        source_path="test.py",
        functions=[
            FunctionNode(name="greet", line_start=1, line_end=3),
        ],
        classes=[
            ClassNode(
                name="Calculator",
                line_start=5,
                line_end=30,
                methods=[
                    FunctionNode(
                        name="add",
                        line_start=6,
                        line_end=10,
                        parameters=[ParameterNode(name="a", type="int"), ParameterNode(name="b", type="int")],
                        return_type="int",
                    ),
                ],
                bases=["BaseCalc"],
            ),
        ],
        imports=[
            ImportNode(name="os", line_start=1, line_end=1),
        ],
        variables=[
            VariableNode(name="VERSION", line_start=2, line_end=2, inferred_type="str"),
        ],
        error_nodes=[],
        parse_time_ms=12.5,
        loc_count=30,
    )


class TestASTTree:
    def test_basic_creation(self):
        tree = ASTTree(language="python")
        assert tree.language == "python"
        assert tree.functions == []
        assert tree.classes == []
        assert tree.imports == []
        assert tree.variables == []
        assert tree.error_nodes == []
        assert tree.parse_time_ms == 0.0
        assert tree.loc_count == 0

    def test_all_functions_includes_top_level(self, sample_tree: ASTTree):
        fns = sample_tree.all_functions(include_nested=False)
        assert len(fns) == 1
        assert fns[0].name == "greet"

    def test_all_functions_includes_nested(self, sample_tree: ASTTree):
        fns = sample_tree.all_functions(include_nested=True)
        names = [f.name for f in fns]
        assert "greet" in names
        assert "add" in names

    def test_all_classes(self, sample_tree: ASTTree):
        classes = sample_tree.all_classes()
        assert len(classes) == 1
        assert classes[0].name == "Calculator"

    def test_all_imports(self, sample_tree: ASTTree):
        imports = sample_tree.all_imports()
        assert len(imports) == 1
        assert imports[0].name == "os"

    def test_traverse_yields_all_nodes(self, sample_tree: ASTTree):
        nodes = list(sample_tree.traverse())
        types = [n.type for n in nodes]
        assert "import" in types
        assert "variable" in types
        assert "function" in types
        assert "class" in types
        assert len(nodes) >= 4

    def test_to_json_and_from_json(self, sample_tree: ASTTree):
        json_str = sample_tree.to_json()
        restored = ASTTree.from_json(json_str)
        assert restored.language == "python"
        assert len(restored.functions) == 1
        assert len(restored.classes) == 1
        assert restored.classes[0].methods[0].name == "add"

    def test_to_dict(self, sample_tree: ASTTree):
        data = sample_tree.to_dict()
        assert isinstance(data, dict)
        assert data["language"] == "python"
        assert len(data["classes"]) == 1

    def test_has_errors_false(self, sample_tree: ASTTree):
        assert sample_tree.has_errors() is False

    def test_has_errors_true(self):
        tree = ASTTree(
            language="python",
            error_nodes=[ErrorNode(line_start=5, line_end=5, message="Syntax error")],
        )
        assert tree.has_errors() is True


class TestHierarchicalStructure:
    def test_class_to_methods_hierarchy(self):
        tree = ASTTree(
            language="python",
            classes=[
                ClassNode(
                    name="Service",
                    line_start=1,
                    line_end=20,
                    methods=[
                        FunctionNode(name="method_a", line_start=3, line_end=8),
                        FunctionNode(name="method_b", line_start=10, line_end=15),
                    ],
                ),
            ],
        )
        svc = tree.classes[0]
        assert len(svc.methods) == 2
        assert svc.methods[0].name == "method_a"
        assert svc.methods[1].name == "method_b"

    def test_function_to_children_hierarchy(self):
        tree = ASTTree(
            language="python",
            functions=[
                FunctionNode(
                    name="outer",
                    line_start=1,
                    line_end=15,
                    children=[
                        FunctionNode(name="inner", line_start=3, line_end=10),
                    ],
                ),
            ],
        )
        outer = tree.functions[0]
        assert len(outer.children) == 1
        assert outer.children[0].name == "inner"

    def test_deep_nesting_class_method_params(self):
        tree = ASTTree(
            language="python",
            classes=[
                ClassNode(
                    name="Deep",
                    line_start=1,
                    line_end=50,
                    methods=[
                        FunctionNode(
                            name="method",
                            line_start=5,
                            line_end=40,
                            parameters=[
                                ParameterNode(name="x", type="int"),
                                ParameterNode(name="y", type="str"),
                            ],
                        ),
                    ],
                ),
            ],
        )
        method = tree.classes[0].methods[0]
        assert len(method.parameters) == 2
        assert method.parameters[0].name == "x"
        assert method.parameters[1].type == "str"


class TestErrorNode:
    def test_creation(self):
        err = ErrorNode(line_start=10, line_end=10, message="Missing colon")
        assert err.type == "error"
        assert err.line_start == 10
        assert err.message == "Missing colon"

    def test_defaults(self):
        err = ErrorNode(line_start=5, line_end=5)
        assert err.message is None
