"""Tests for User model."""

import uuid

from sqlalchemy import inspect

from app.models.base import TimestampMixin, UUIDMixin
from app.models.user import User


class TestUserModel:
    def test_inherits_uuid_mixin(self):
        assert issubclass(User, UUIDMixin)

    def test_inherits_timestamp_mixin(self):
        assert issubclass(User, TimestampMixin)

    def test_tablename(self):
        assert User.__tablename__ == "users"

    def test_has_email_column(self):
        mapper = inspect(User)
        assert "email" in mapper.columns

    def test_email_is_unique(self):
        mapper = inspect(User)
        col = mapper.columns["email"]
        assert col.unique

    def test_has_password_hash_column(self):
        mapper = inspect(User)
        assert "password_hash" in mapper.columns

    def test_has_name_column(self):
        mapper = inspect(User)
        assert "name" in mapper.columns

    def test_has_is_admin_column(self):
        mapper = inspect(User)
        assert "is_admin" in mapper.columns

    def test_has_is_active_column(self):
        mapper = inspect(User)
        assert "is_active" in mapper.columns

    def test_has_last_login_at_column(self):
        mapper = inspect(User)
        assert "last_login_at" in mapper.columns

    def test_last_login_at_is_nullable(self):
        mapper = inspect(User)
        col = mapper.columns["last_login_at"]
        assert col.nullable

    def test_has_email_verified_at_column(self):
        mapper = inspect(User)
        assert "email_verified_at" in mapper.columns

    def test_repr(self):
        user = User(id=uuid.uuid4(), email="test@example.com", is_admin=False)
        repr_str = repr(user)
        assert "test@example.com" in repr_str
