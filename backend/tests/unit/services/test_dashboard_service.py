"""Unit tests for dashboard_service helpers — Epic 6, Story 6.1.

Focus on pure functions (no DB / Redis). Aggregation queries are covered
by integration tests in tests/integration/test_dashboard_routes.py.
"""

from types import SimpleNamespace

from app.services.dashboard_service import _is_owner_or_admin


class TestIsOwnerOrAdmin:
    def test_admin_user_returns_true(self):
        user = SimpleNamespace(is_admin=True, _tenant_role="user")
        assert _is_owner_or_admin(user) is True

    def test_owner_role_returns_true(self):
        user = SimpleNamespace(is_admin=False, _tenant_role="owner")
        assert _is_owner_or_admin(user) is True

    def test_regular_user_returns_false(self):
        user = SimpleNamespace(is_admin=False, _tenant_role="user")
        assert _is_owner_or_admin(user) is False

    def test_missing_tenant_role_attr_defaults_to_user(self):
        user = SimpleNamespace(is_admin=False)
        assert _is_owner_or_admin(user) is False
