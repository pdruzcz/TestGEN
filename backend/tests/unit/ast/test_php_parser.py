"""Tests for PhpAdapter (Story 1.52 / FR12)."""

import pytest

from app.services.analysis.ast.adapters.php_parser import PhpAdapter
from app.services.analysis.ast.registry import ASTParserRegistry


@pytest.fixture
def parser():
    return PhpAdapter()


# ── Method / function extraction ──────────────────────────────────


class TestPhpFunctions:
    def test_top_level_function(self, parser):
        code = "<?php\nfunction helper(int $x): void {\n    echo $x;\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 1
        fn = tree.functions[0]
        assert fn.name == "helper"
        assert fn.type == "function"
        assert fn.return_type == "void"
        assert len(fn.parameters) == 1
        assert fn.parameters[0].name == "x"
        assert fn.parameters[0].type == "int"

    def test_function_default_param(self, parser):
        code = "<?php\nfunction add(int $a, int $b = 1): int {\n    return $a + $b;\n}\n"
        tree = parser.parse(code)
        fn = tree.functions[0]
        assert fn.parameters[1].name == "b"
        assert fn.parameters[1].type == "int"

    def test_multiple_top_level_functions(self, parser):
        code = "<?php\nfunction a() {}\nfunction b() {}\nfunction c() {}\n"
        tree = parser.parse(code)
        assert [f.name for f in tree.functions] == ["a", "b", "c"]

    def test_methods_not_in_top_level_functions(self, parser):
        code = "<?php\nclass Foo {\n    public function bar() {}\n}\n"
        tree = parser.parse(code)
        assert len(tree.functions) == 0
        assert len(tree.classes[0].methods) == 1


class TestPhpMethods:
    def test_simple_method(self, parser):
        code = "<?php\nclass Foo {\n    public function bar(): void {\n        echo 1;\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.name == "bar"
        assert method.return_type == "void"

    def test_method_with_params(self, parser):
        code = "<?php\nclass Foo {\n    public function greet(string $name, int $age): string {\n        return $name;\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert len(method.parameters) == 2
        assert method.parameters[0].name == "name"
        assert method.parameters[0].type == "string"
        assert method.parameters[1].name == "age"
        assert method.parameters[1].type == "int"
        assert method.return_type == "string"

    def test_constructor(self, parser):
        code = "<?php\nclass Foo {\n    public function __construct(int $x) {\n        $this->x = $x;\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.name == "__construct"
        assert method.type == "constructor"

    def test_static_method(self, parser):
        code = "<?php\nclass Foo {\n    public static function create(array $data): self {\n        return new self();\n    }\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.name == "create"
        assert method.parameters[0].type == "array"

    def test_abstract_method_no_body(self, parser):
        code = "<?php\nabstract class Foo {\n    abstract public function execute(int $id): bool;\n}\n"
        tree = parser.parse(code)
        method = tree.classes[0].methods[0]
        assert method.name == "execute"
        assert method.return_type == "bool"

    def test_method_with_attribute(self, parser):
        """PHP 8 attribute prefixed method must still be extracted."""
        code = (
            "<?php\nclass Foo {\n"
            "    #[Route(path: '/x', methods: ['GET'])]\n"
            "    public function show(int $id): Response {\n        return null;\n    }\n}\n"
        )
        tree = parser.parse(code)
        assert len(tree.classes[0].methods) == 1
        method = tree.classes[0].methods[0]
        assert method.name == "show"
        assert method.return_type == "Response"


# ── Return / parameter type variants (AC5) ────────────────────────


class TestPhpTypes:
    def test_nullable_return_type(self, parser):
        code = "<?php\nclass A {\n    public function find(int $id): ?array {\n        return null;\n    }\n}\n"
        tree = parser.parse(code)
        assert tree.classes[0].methods[0].return_type == "?array"

    def test_union_return_type(self, parser):
        code = "<?php\nclass A {\n    public function parse($x): int|string {\n        return 0;\n    }\n}\n"
        tree = parser.parse(code)
        assert tree.classes[0].methods[0].return_type == "int|string"

    def test_typed_parameter(self, parser):
        code = "<?php\nclass A {\n    public function set(UserRepo $repo): void {}\n}\n"
        tree = parser.parse(code)
        param = tree.classes[0].methods[0].parameters[0]
        assert param.name == "repo"
        assert param.type == "UserRepo"

    def test_match_expression_complexity(self, parser):
        code = (
            "<?php\nfunction label(Status $s): string {\n"
            "    return match ($s) {\n"
            "        Status::Active => 'a',\n"
            "        default => 'z',\n"
            "    };\n}\n"
        )
        tree = parser.parse(code)
        assert tree.functions[0].complexity >= 2


# ── Class extraction ──────────────────────────────────────────────


class TestPhpClasses:
    def test_simple_class(self, parser):
        code = "<?php\nclass UserService {\n}\n"
        tree = parser.parse(code)
        assert len(tree.classes) == 1
        assert tree.classes[0].name == "UserService"
        assert tree.classes[0].type == "class"

    def test_class_extends_and_implements(self, parser):
        code = "<?php\nclass UserController extends BaseController implements Repo, Cacheable {\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert "BaseController" in cls.bases
        assert "Repo" in cls.bases
        assert "Cacheable" in cls.bases

    def test_interface(self, parser):
        code = "<?php\ninterface Repository {\n    public function find(int $id): ?array;\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert cls.name == "Repository"
        assert cls.type == "interface"
        assert len(cls.methods) == 1

    def test_trait(self, parser):
        code = "<?php\ntrait Cacheable {\n    public function cached(): void {}\n}\n"
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert cls.type == "trait"
        assert cls.name == "Cacheable"

    def test_enum_php81(self, parser):
        code = (
            "<?php\nenum Status: string {\n"
            "    case Active = 'active';\n"
            "    public function label(): string {\n        return $this->value;\n    }\n}\n"
        )
        tree = parser.parse(code)
        cls = tree.classes[0]
        assert cls.type == "enum"
        assert cls.name == "Status"
        assert len(cls.methods) == 1
        assert cls.methods[0].name == "label"

    def test_nested_class_not_supported_flat_list(self, parser):
        """PHP adapters record all top-level + nested class-likes in the flat list."""
        code = "<?php\nclass Outer {\n    public function a() {}\n}\nclass Inner {\n}\n"
        tree = parser.parse(code)
        names = [c.name for c in tree.classes]
        assert "Outer" in names
        assert "Inner" in names


# ── Import (use) extraction ───────────────────────────────────────


class TestPhpImports:
    def test_simple_use(self, parser):
        code = "<?php\nuse App\\Service;\nclass Foo {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 1
        assert tree.imports[0].module == "App\\Service"

    def test_aliased_use(self, parser):
        code = "<?php\nuse App\\Contracts\\Foo as Bar;\nclass Foo {}\n"
        tree = parser.parse(code)
        imp = tree.imports[0]
        assert imp.module == "App\\Contracts\\Foo"
        assert "Bar" in imp.aliases

    def test_multiple_uses(self, parser):
        code = "<?php\nuse App\\A;\nuse App\\B;\nuse App\\C;\nclass Foo {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 3

    def test_grouped_use(self, parser):
        code = "<?php\nuse App\\A, App\\B;\nclass Foo {}\n"
        tree = parser.parse(code)
        assert len(tree.imports) == 2
        modules = {i.module for i in tree.imports}
        assert "App\\A" in modules
        assert "App\\B" in modules


# ── Integration / registry / error recovery ──────────────────────


class TestPhpAdapterIntegration:
    def test_registry_registered(self):
        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("php")
        parser = registry.get_parser("php")
        assert isinstance(parser, PhpAdapter)

    def test_adapter_loaded_in_init(self):
        from app.services.analysis.ast.adapters import LOADED_ADAPTERS

        assert "php_parser" in LOADED_ADAPTERS

    def test_full_php_file(self, parser):
        code = (
            "<?php\n"
            "namespace App\\Service;\n\n"
            "use App\\Repo\\UserRepo;\n"
            "use App\\Contracts\\Cacheable as C;\n\n"
            "class UserService {\n"
            "    public function __construct(private UserRepo $repo) {}\n"
            "\n"
            "    public function find(int $id): ?User {\n"
            "        if ($id <= 0) { return null; }\n"
            "        return $this->repo->find($id);\n"
            "    }\n"
            "}\n\n"
            "function helper(): void {}\n"
        )
        tree = parser.parse(code)
        assert len(tree.imports) == 2
        assert len(tree.classes) == 1
        cls = tree.classes[0]
        assert cls.name == "UserService"
        assert len(cls.methods) == 2
        # top-level function counted separately
        assert [f.name for f in tree.functions] == ["helper"]
        find = next(m for m in cls.methods if m.name == "find")
        assert find.return_type == "?User"
        assert find.complexity >= 2  # has an if

    def test_error_recovery(self, parser):
        code = "<?php\nclass Foo {\n    broken syntax !!!\n}\n"
        tree = parser.parse(code)
        assert tree.has_errors()

    def test_empty_code(self, parser):
        tree = parser.parse("")
        assert tree.functions == []
        assert tree.classes == []
        assert tree.imports == []

    def test_language_property(self, parser):
        assert parser.language == "php"

    def test_no_double_count_across_functions_and_methods(self, parser):
        code = "<?php\nclass Foo {\n    public function a() {}\n}\nfunction b() {}\n"
        tree = parser.parse(code)
        assert [f.name for f in tree.functions] == ["b"]
        assert [m.name for m in tree.classes[0].methods] == ["a"]
