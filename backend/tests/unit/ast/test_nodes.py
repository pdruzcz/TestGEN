from app.services.analysis.ast.nodes import (
    BaseASTNode,
    ClassNode,
    FunctionNode,
    ImportNode,
    ParameterNode,
    VariableNode,
)


class TestParameterNode:
    def test_basic_creation(self):
        p = ParameterNode(name="x")
        assert p.name == "x"
        assert p.type is None
        assert p.default_value is None

    def test_full_creation(self):
        p = ParameterNode(name="count", type="int", default_value="0", line_start=5)
        assert p.name == "count"
        assert p.type == "int"
        assert p.default_value == "0"
        assert p.line_start == 5

    def test_serialization(self):
        p = ParameterNode(name="items", type="list[str]")
        data = p.model_dump()
        assert data["name"] == "items"
        assert data["type"] == "list[str]"
        restored = ParameterNode.model_validate(data)
        assert restored == p


class TestFunctionNode:
    def test_basic_creation(self):
        fn = FunctionNode(name="hello", line_start=1, line_end=5)
        assert fn.name == "hello"
        assert fn.type == "function"
        assert fn.line_start == 1
        assert fn.line_end == 5
        assert fn.docstring is None
        assert fn.parameters == []
        assert fn.return_type is None
        assert fn.complexity == 1
        assert fn.children == []

    def test_full_creation(self):
        params = [
            ParameterNode(name="x", type="int"),
            ParameterNode(name="y", type="int"),
        ]
        fn = FunctionNode(
            name="add",
            line_start=10,
            line_end=15,
            docstring="Add two numbers.",
            parameters=params,
            return_type="int",
            complexity=2,
        )
        assert fn.name == "add"
        assert len(fn.parameters) == 2
        assert fn.docstring == "Add two numbers."
        assert fn.complexity == 2

    def test_nested_functions(self):
        inner = FunctionNode(name="helper", line_start=3, line_end=5)
        outer = FunctionNode(name="outer", line_start=1, line_end=10, children=[inner])
        assert len(outer.children) == 1
        assert outer.children[0].name == "helper"

    def test_serialization_roundtrip(self):
        fn = FunctionNode(
            name="compute",
            line_start=1,
            line_end=20,
            parameters=[ParameterNode(name="data", type="list[int]")],
            return_type="dict",
            complexity=5,
        )
        json_str = fn.model_dump_json()
        restored = FunctionNode.model_validate_json(json_str)
        assert restored == fn


class TestClassNode:
    def test_basic_creation(self):
        cls = ClassNode(name="MyClass", line_start=1, line_end=50)
        assert cls.name == "MyClass"
        assert cls.type == "class"
        assert cls.methods == []
        assert cls.bases == []

    def test_with_methods_and_bases(self):
        methods = [
            FunctionNode(name="__init__", line_start=3, line_end=10),
            FunctionNode(name="process", line_start=12, line_end=25),
        ]
        cls = ClassNode(
            name="Service",
            line_start=1,
            line_end=30,
            methods=methods,
            bases=["BaseService", "Mixin"],
            docstring="Service class.",
        )
        assert len(cls.methods) == 2
        assert cls.bases == ["BaseService", "Mixin"]
        assert cls.docstring == "Service class."

    def test_serialization_roundtrip(self):
        cls = ClassNode(
            name="Handler",
            line_start=5,
            line_end=100,
            methods=[FunctionNode(name="handle", line_start=10, line_end=20)],
            bases=["BaseHandler"],
        )
        data = cls.model_dump()
        restored = ClassNode.model_validate(data)
        assert restored == cls


class TestImportNode:
    def test_basic_creation(self):
        imp = ImportNode(name="os", line_start=1, line_end=1)
        assert imp.name == "os"
        assert imp.type == "import"
        assert imp.module is None
        assert imp.aliases == []

    def test_from_import(self):
        imp = ImportNode(
            name="path",
            line_start=2,
            line_end=2,
            module="os.path",
            aliases=["join", "exists"],
        )
        assert imp.module == "os.path"
        assert imp.aliases == ["join", "exists"]

    def test_serialization_roundtrip(self):
        imp = ImportNode(name="List", line_start=1, line_end=1, module="typing", aliases=["Dict"])
        json_str = imp.model_dump_json()
        restored = ImportNode.model_validate_json(json_str)
        assert restored == imp


class TestVariableNode:
    def test_basic_creation(self):
        var = VariableNode(name="count", line_start=5, line_end=5)
        assert var.name == "count"
        assert var.type == "variable"
        assert var.inferred_type is None

    def test_with_inferred_type(self):
        var = VariableNode(name="items", line_start=5, line_end=5, inferred_type="list[int]")
        assert var.inferred_type == "list[int]"

    def test_serialization_roundtrip(self):
        var = VariableNode(name="config", line_start=1, line_end=1, inferred_type="dict")
        data = var.model_dump()
        restored = VariableNode.model_validate(data)
        assert restored == var


class TestBaseASTNode:
    def test_all_nodes_inherit_from_base(self):
        fn = FunctionNode(name="f", line_start=1, line_end=2)
        cls = ClassNode(name="C", line_start=1, line_end=2)
        imp = ImportNode(name="os", line_start=1, line_end=1)
        var = VariableNode(name="x", line_start=1, line_end=1)
        assert isinstance(fn, BaseASTNode)
        assert isinstance(cls, BaseASTNode)
        assert isinstance(imp, BaseASTNode)
        assert isinstance(var, BaseASTNode)

    def test_base_fields_present_on_all_nodes(self):
        fn = FunctionNode(name="f", line_start=1, line_end=5)
        assert hasattr(fn, "docstring")
        assert hasattr(fn, "parameters")
        assert hasattr(fn, "return_type")
        assert hasattr(fn, "complexity")
        assert fn.complexity == 1
