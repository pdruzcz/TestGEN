import pytest

from app.services.analysis.ast.registry import ASTParserRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset AST parser registry between test modules."""
    ASTParserRegistry.reset_instance()
    yield
    ASTParserRegistry.reset_instance()
