"""Unit tests for RBAC require_role dependency factory."""

from unittest.mock import MagicMock

import pytest

from app.core.dependencies import require_role
from app.core.exceptions import ForbiddenError


def _make_request_state(role: str = "user", is_admin: bool = False) -> MagicMock:
    """Create a mock request with state.role and state.is_admin attributes."""
    request = MagicMock()
    request.state.role = role
    request.state.is_admin = is_admin
    return request


class TestRequireRole:
    async def test_owner_passes_owner_check(self):
        checker = require_role("owner")
        user = MagicMock()
        request = _make_request_state(role="owner", is_admin=False)

        result = await checker(request=request, current_user=user)
        assert result == user

    async def test_user_fails_owner_check(self):
        checker = require_role("owner")
        user = MagicMock()
        request = _make_request_state(role="user", is_admin=False)

        with pytest.raises(ForbiddenError):
            await checker(request=request, current_user=user)

    async def test_admin_passes_owner_check_via_bypass(self):
        """Admin bypasses all role checks regardless of tenant role."""
        checker = require_role("owner")
        user = MagicMock()
        request = _make_request_state(role="user", is_admin=True)

        result = await checker(request=request, current_user=user)
        assert result == user

    async def test_admin_passes_admin_check(self):
        checker = require_role("admin")
        user = MagicMock()
        request = _make_request_state(role="admin", is_admin=True)

        result = await checker(request=request, current_user=user)
        assert result == user
