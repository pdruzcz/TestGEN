import pytest

from app.services.analysis.ast.base_parser import BaseASTParser
from app.services.analysis.ast.registry import (
    ASTParserRegistry,
    UnsupportedLanguageError,
    register_parser,
)


class FakeParser(BaseASTParser):
    language = "fake"
    _ts_language = None

    def extract_functions(self, source_code, tree=None):
        return []

    def extract_classes(self, source_code, tree=None):
        return []

    def extract_imports(self, source_code, tree=None):
        return []


class AnotherFakeParser(BaseASTParser):
    language = "other"
    _ts_language = None

    def extract_functions(self, source_code, tree=None):
        return []

    def extract_classes(self, source_code, tree=None):
        return []

    def extract_imports(self, source_code, tree=None):
        return []


@pytest.fixture(autouse=True)
def reset_registry():
    ASTParserRegistry.reset_instance()
    yield
    ASTParserRegistry.reset_instance()


class TestASTParserRegistry:
    def test_singleton(self):
        r1 = ASTParserRegistry.get_instance()
        r2 = ASTParserRegistry.get_instance()
        assert r1 is r2

    def test_register_and_get_parser(self):
        registry = ASTParserRegistry.get_instance()
        registry.register("python", FakeParser)
        parser = registry.get_parser("python")
        assert isinstance(parser, FakeParser)

    def test_register_case_insensitive(self):
        registry = ASTParserRegistry.get_instance()
        registry.register("Python", FakeParser)
        parser = registry.get_parser("python")
        assert isinstance(parser, FakeParser)

    def test_get_parser_unsupported_language(self):
        registry = ASTParserRegistry.get_instance()
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            registry.get_parser("cobol")
        assert "cobol" in str(exc_info.value)
        assert exc_info.value.language == "cobol"

    def test_unsupported_language_error_lists_supported(self):
        registry = ASTParserRegistry.get_instance()
        registry.register("python", FakeParser)
        registry.register("java", AnotherFakeParser)
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            registry.get_parser("rust")
        assert "python" in str(exc_info.value)
        assert "java" in str(exc_info.value)

    def test_is_supported(self):
        registry = ASTParserRegistry.get_instance()
        registry.register("python", FakeParser)
        assert registry.is_supported("python") is True
        assert registry.is_supported("ruby") is False

    def test_supported_languages(self):
        registry = ASTParserRegistry.get_instance()
        registry.register("java", AnotherFakeParser)
        registry.register("python", FakeParser)
        langs = registry.supported_languages()
        assert "java" in langs
        assert "python" in langs

    def test_get_parser_returns_new_instance(self):
        registry = ASTParserRegistry.get_instance()
        registry.register("python", FakeParser)
        p1 = registry.get_parser("python")
        p2 = registry.get_parser("python")
        assert p1 is not p2


class TestRegisterParserDecorator:
    def test_decorator_registers_parser(self):
        @register_parser("decorated")
        class DecoratedParser(BaseASTParser):
            language = "decorated"
            _ts_language = None

            def extract_functions(self, source_code, tree=None):
                return []

            def extract_classes(self, source_code, tree=None):
                return []

            def extract_imports(self, source_code, tree=None):
                return []

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("decorated")
        parser = registry.get_parser("decorated")
        assert isinstance(parser, DecoratedParser)

    def test_decorator_returns_class(self):
        @register_parser("test_class_return")
        class TestParser(BaseASTParser):
            language = "test_class_return"
            _ts_language = None

            def extract_functions(self, source_code, tree=None):
                return []

            def extract_classes(self, source_code, tree=None):
                return []

            def extract_imports(self, source_code, tree=None):
                return []

        assert issubclass(TestParser, BaseASTParser)

    def test_decorator_survives_reset_instance(self):
        @register_parser("resilient")
        class ResilientParser(BaseASTParser):
            language = "resilient"
            _ts_language = None

            def extract_functions(self, source_code, tree=None):
                return []

            def extract_classes(self, source_code, tree=None):
                return []

            def extract_imports(self, source_code, tree=None):
                return []

        registry = ASTParserRegistry.get_instance()
        assert registry.is_supported("resilient")
        ASTParserRegistry.reset_instance()
        registry2 = ASTParserRegistry.get_instance()
        assert registry2.is_supported("resilient")
        parser = registry2.get_parser("resilient")
        assert isinstance(parser, ResilientParser)
