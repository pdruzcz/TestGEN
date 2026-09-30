"""Shared fixtures for integration tests."""

import pytest

# Import all AST parser adapters to ensure they register themselves
from app.services.analysis.ast.adapters.c_adapter import CAdapter  # noqa: F401
from app.services.analysis.ast.adapters.cpp_parser import CppAdapter  # noqa: F401
from app.services.analysis.ast.adapters.csharp_parser import CSharpAdapter  # noqa: F401
from app.services.analysis.ast.adapters.java_parser import JavaAdapter  # noqa: F401
from app.services.analysis.ast.adapters.javascript_parser import JavaScriptAdapter  # noqa: F401
from app.services.analysis.ast.adapters.python_parser import PythonAdapter  # noqa: F401
from app.services.analysis.ast.adapters.typescript_parser import TypeScriptAdapter  # noqa: F401


@pytest.fixture(autouse=True, scope="session")
def register_parsers():
    """Ensure all AST parsers are registered before running integration tests."""
    # The parsers are already registered via the @register_parser decorator
    # during import above. This fixture just ensures the imports happen.
    pass


@pytest.fixture(autouse=True)
def _bypass_feature_gating(monkeypatch):
    """Story 7.13 — domyślnie pomiń gating modułów w testach integracyjnych.

    Testy integracyjne weryfikują logikę modułów, nie dostęp planu; bypass
    nie wykonuje żadnych zapytań DB, więc sekwencje ``db.execute`` w mockach
    pozostają nienaruszone. Egzekwowanie 402 mają własne testy
    (tests/api/test_billing_features.py + tests/services/test_feature_gating.py).
    """

    async def _noop(self, tenant_id, module: str) -> None:
        return None

    monkeypatch.setattr(
        "app.services.billing.feature_gating.FeatureGatingService.enforce_feature",
        _noop,
    )
