"""Unit tests for Redis token store operations."""

import uuid

import pytest
from fakeredis.aioredis import FakeRedis

from app.services.auth.token_store import (
    blacklist_access_token,
    clear_login_attempts,
    get_login_attempts,
    increment_login_attempts,
    is_access_token_blacklisted,
    is_account_locked,
    is_refresh_token_valid,
    lock_account,
    revoke_refresh_token,
    store_refresh_token,
)


@pytest.fixture
async def redis():
    return FakeRedis(decode_responses=True)


@pytest.fixture
def user_id():
    return uuid.uuid4()


class TestRefreshTokenStore:
    async def test_store_and_validate(self, redis, user_id):
        jti = str(uuid.uuid4())
        await store_refresh_token(redis, jti, user_id, 3600)
        assert await is_refresh_token_valid(redis, jti) is True

    async def test_revoke_invalidates(self, redis, user_id):
        jti = str(uuid.uuid4())
        await store_refresh_token(redis, jti, user_id, 3600)
        await revoke_refresh_token(redis, jti)
        assert await is_refresh_token_valid(redis, jti) is False

    async def test_nonexistent_jti_invalid(self, redis):
        assert await is_refresh_token_valid(redis, "nonexistent") is False


class TestAccessTokenBlacklist:
    async def test_blacklist_and_check(self, redis):
        jti = str(uuid.uuid4())
        await blacklist_access_token(redis, jti, 300)
        assert await is_access_token_blacklisted(redis, jti) is True

    async def test_non_blacklisted_token(self, redis):
        assert await is_access_token_blacklisted(redis, "clean-jti") is False

    async def test_zero_ttl_not_stored(self, redis):
        jti = str(uuid.uuid4())
        await blacklist_access_token(redis, jti, 0)
        assert await is_access_token_blacklisted(redis, jti) is False


class TestLoginAttempts:
    async def test_increment_and_get(self, redis, user_id):
        count = await increment_login_attempts(redis, user_id)
        assert count == 1
        assert await get_login_attempts(redis, user_id) == 1

    async def test_multiple_increments(self, redis, user_id):
        for _i in range(5):
            count = await increment_login_attempts(redis, user_id)
        assert count == 5

    async def test_clear_resets_counter(self, redis, user_id):
        await increment_login_attempts(redis, user_id)
        await increment_login_attempts(redis, user_id)
        await clear_login_attempts(redis, user_id)
        assert await get_login_attempts(redis, user_id) == 0

    async def test_get_nonexistent_returns_zero(self, redis, user_id):
        assert await get_login_attempts(redis, user_id) == 0


class TestAccountLock:
    async def test_lock_and_check(self, redis, user_id):
        await lock_account(redis, user_id)
        assert await is_account_locked(redis, user_id) is True

    async def test_not_locked_by_default(self, redis, user_id):
        assert await is_account_locked(redis, user_id) is False
