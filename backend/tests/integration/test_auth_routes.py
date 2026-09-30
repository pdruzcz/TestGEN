"""Integration tests for auth API routes — real PostgreSQL database.

These tests exercise the full route→service→DB flow using a real
PostgreSQL database. Each test runs inside a transaction that is
rolled back after the test (no persistent side effects).
"""

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.redis import get_redis
from app.main import create_app

_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://testgen:testgen_dev_password@localhost:5432/testgen",  # BYPASSRLS role for app-level tests
)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def db_app(app):
    """App wired to real PostgreSQL with per-test transaction rollback."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_TEST_DB_URL, pool_size=1)

    async with engine.connect() as conn:
        txn = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        async def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db

        yield app, session

        app.dependency_overrides.clear()
        await session.close()
        await txn.rollback()

    await engine.dispose()


class TestRegisterRoute:
    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_register_success_201_real_db(self, mock_email_task, db_app):
        """Full integration: register creates tenant + user in real PostgreSQL."""
        app, session = db_app

        # Grant BYPASSRLS temporarily for this session (service sets RLS context)
        await session.execute(text("SET LOCAL app.current_tenant = '00000000-0000-0000-0000-000000000000'"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test-{uuid.uuid4().hex[:8]}@test.com",
                    "password": "StrongPass12345!",
                    "company_name": "Acme Corp Test",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert "email" in data
        assert "location" in {k.lower() for k in response.headers}

    async def test_register_weak_password_422(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "a@b.com",
                "password": "short",
                "company_name": "X",
            },
        )
        assert response.status_code == 422

    async def test_register_invalid_email_422(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "StrongPass12345!",
                "company_name": "X",
            },
        )
        assert response.status_code == 422

    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_register_duplicate_returns_201_no_enumeration(self, mock_email_task, db_app):
        """Anti-enumeration: duplicate email returns 201 (same as success)."""
        app, _session = db_app
        email = f"dup-{uuid.uuid4().hex[:8]}@test.com"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # First registration — creates user
            resp1 = await ac.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "StrongPass12345!", "company_name": "X"},
            )
            assert resp1.status_code == 201

            # Second registration — duplicate email, still returns 201
            resp2 = await ac.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "StrongPass12345!", "company_name": "Y"},
            )
            assert resp2.status_code == 201
            assert resp2.json()["email"] == email

    async def test_register_missing_complexity_422(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@test.com",
                "password": "alllowercase12",
                "company_name": "Test",
            },
        )
        assert response.status_code == 422

    async def test_register_rfc7807_validation_format(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid",
                "password": "x",
                "company_name": "",
            },
        )
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://testgen.io/errors/validation-error"
        assert data["title"] == "Validation Error"
        assert data["status"] == 422
        assert "errors" in data

    async def test_register_nip_invalid_format_422(self, client):
        """H4: NIP schema rejects non-digit strings at Pydantic level."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "nip@test.com",
                "password": "StrongPass12345!",
                "company_name": "Test",
                "nip": "abc",
            },
        )
        assert response.status_code == 422


class TestVerifyEmailRoute:
    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_verify_email_full_flow(self, mock_email_task, db_app):
        """Full integration: register → verify email → user activated."""
        app, session = db_app
        email = f"verify-{uuid.uuid4().hex[:8]}@test.com"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Register
            resp = await ac.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "StrongPass12345!", "company_name": "VerifyCo"},
            )
            assert resp.status_code == 201

        # Find the verification token in DB
        result = await session.execute(
            text("SELECT token FROM email_verifications WHERE type = 'registration' ORDER BY created_at DESC LIMIT 1")
        )
        token = result.scalar_one()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/verify-email",
                json={"token": token},
            )
            assert resp.status_code == 200
            assert resp.json()["message"] == "Adres e-mail został zweryfikowany"
            assert "email" not in resp.json()  # no email leakage


class TestAcceptInvitationRoute:
    async def test_accept_invitation_weak_password_422(self, client):
        response = await client.post(
            "/api/v1/auth/accept-invitation",
            json={"token": "valid_token", "password": "short"},
        )
        assert response.status_code == 422

    async def test_accept_invitation_missing_token_422(self, client):
        response = await client.post(
            "/api/v1/auth/accept-invitation",
            json={"password": "StrongPass12345!"},
        )
        assert response.status_code == 422


class TestRefreshTokenRejection:
    async def test_refresh_token_rejected_on_protected_endpoint(self, app):
        """Using a refresh token to access a protected endpoint must return 401."""

        from app.core.dependencies import get_db
        from app.services.auth.jwt_handler import create_refresh_token

        user_id = uuid.uuid4()
        refresh_token = create_refresh_token(user_id)

        mock_session = AsyncMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {refresh_token}"},
            )

        assert response.status_code == 401
        app.dependency_overrides.clear()


def _parse_set_cookies(headers) -> dict[str, dict]:
    """Parse Set-Cookie headers into {name: {value, httponly, secure, samesite, path, max-age}}."""
    result = {}
    for raw in headers.get_list("set-cookie"):
        parts = raw.split(";")
        name, _, val = parts[0].partition("=")
        attrs = {"value": val}
        for part in parts[1:]:
            k, _, v = part.strip().partition("=")
            attrs[k.strip().lower()] = v.strip() if v else True
        result[name.strip()] = attrs
    return result


def _csrf_headers(resp) -> dict[str, str]:
    """Extract CSRF token from Set-Cookie and return as X-XSRF-TOKEN header dict."""
    cookies = _parse_set_cookies(resp.headers)
    token = cookies.get("XSRF-TOKEN", {}).get("value", "")
    return {"X-XSRF-TOKEN": token} if token else {}


@pytest.fixture
async def registered_user(db_app):
    """Helper: register + verify a user, return (app, session, email, password, fake_redis)."""
    app, session = db_app
    fake_redis = FakeRedis(decode_responses=True)

    async def override_redis():
        return fake_redis

    app.dependency_overrides[get_redis] = override_redis

    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    password = "StrongPass12345!"

    with patch("app.api.routes.auth.send_verification_email_task"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "company_name": "TestCo"},
            )

    # Verify email directly in DB
    result = await session.execute(
        text("SELECT token FROM email_verifications WHERE type = 'registration' ORDER BY created_at DESC LIMIT 1")
    )
    token = result.scalar_one()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/auth/verify-email", json={"token": token})

    return app, session, email, password, fake_redis


class TestLoginRoute:
    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_login_success_sets_httponly_cookies_with_jwt(self, mock_email_task, registered_user):
        """AC1: login → access_token + refresh_token in HttpOnly cookies with correct attributes."""
        app, _session, email, password, _fake_redis = registered_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["mfa_required"] is False
        assert data["mfa_token"] is None

        cookies = _parse_set_cookies(resp.headers)
        assert "access_token" in cookies
        assert "refresh_token" in cookies

        # H2: Verify HttpOnly flag
        assert cookies["access_token"].get("httponly") is True
        assert cookies["refresh_token"].get("httponly") is True

        # Verify SameSite and Path
        assert cookies["access_token"].get("samesite", "").lower() == "lax"
        assert cookies["refresh_token"].get("samesite", "").lower() == "lax"
        assert cookies["access_token"].get("path") == "/api"
        assert cookies["refresh_token"].get("path") == "/api/v1/auth"

        # Verify JWT payload structure
        from app.services.auth.jwt_handler import decode_token

        access_jwt = cookies["access_token"]["value"]
        payload = decode_token(access_jwt)
        assert "sub" in payload
        assert "tenant_id" in payload
        assert "role" in payload
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload  # H2: jti must be present
        assert payload["type"] == "access"

    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_login_wrong_password_401(self, mock_email_task, registered_user):
        """AC1: wrong password returns 401 with generic message (no email enumeration)."""
        app, _session, email, _password, _fake_redis = registered_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "WrongPassword123!"},
            )

        assert resp.status_code == 401
        data = resp.json()
        assert "Invalid credentials" in data.get("detail", "")

    async def test_login_nonexistent_user_401(self, app):
        """AC1: nonexistent email returns same 401 (no enumeration)."""
        fake_redis = FakeRedis(decode_responses=True)

        async def override_redis():
            return fake_redis

        app.dependency_overrides[get_redis] = override_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent@test.com", "password": "WrongPass123!"},
            )

        assert resp.status_code == 401
        app.dependency_overrides.clear()


class TestRefreshRoute:
    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_refresh_token_rotation(self, mock_email_task, registered_user):
        """AC2: refresh rotates tokens — old refresh revoked, new tokens issued."""
        app, _session, email, password, _fake_redis = registered_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Login to get tokens
            login_resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert login_resp.status_code == 200
            login_cookies = _parse_set_cookies(login_resp.headers)
            original_refresh = login_cookies["refresh_token"]["value"]
            csrf = _csrf_headers(login_resp)

            # Refresh
            refresh_resp = await ac.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": original_refresh},
                headers=csrf,
            )

        assert refresh_resp.status_code == 200
        refresh_cookies = _parse_set_cookies(refresh_resp.headers)
        assert "access_token" in refresh_cookies
        assert "refresh_token" in refresh_cookies

        # New refresh token is different from old one (rotation)
        new_refresh = refresh_cookies["refresh_token"]["value"]
        assert new_refresh != original_refresh

    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_refresh_revoked_token_401(self, mock_email_task, registered_user):
        """AC2: using a revoked refresh token returns 401."""
        app, _session, email, password, _fake_redis = registered_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Login
            login_resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            login_cookies = _parse_set_cookies(login_resp.headers)
            original_refresh = login_cookies["refresh_token"]["value"]
            csrf = _csrf_headers(login_resp)

            # Refresh once (revokes original)
            await ac.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": original_refresh},
                headers=csrf,
            )

            # Try to use revoked token again
            resp = await ac.post(
                "/api/v1/auth/refresh",
                cookies={"refresh_token": original_refresh},
                headers=csrf,
            )

        assert resp.status_code == 401

    async def test_refresh_missing_cookie_401(self, app):
        """AC3: missing refresh token → 401."""
        fake_redis = FakeRedis(decode_responses=True)

        async def override_redis():
            return fake_redis

        app.dependency_overrides[get_redis] = override_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/auth/refresh")

        assert resp.status_code == 401
        app.dependency_overrides.clear()


class TestBruteForceProtection:
    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_account_locked_after_5_failed_attempts(self, mock_email_task, registered_user):
        """AC6: 5 failed login attempts → 429 Too Many Requests with Retry-After."""
        app, _session, email, _password, _fake_redis = registered_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 5 failed attempts
            for _ in range(5):
                resp = await ac.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "WrongPassword123!"},
                )
                assert resp.status_code == 401

            # 6th attempt → 429 locked
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "WrongPassword123!"},
            )

        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_correct_password_rejected_when_locked(self, mock_email_task, registered_user):
        """AC6: even correct password rejected during lockout."""
        app, _session, email, password, _fake_redis = registered_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Lock account
            for _ in range(5):
                await ac.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "WrongPassword123!"},
                )

            # Correct password still rejected
            resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )

        assert resp.status_code == 429


class TestLogoutRoute:
    @patch("app.api.routes.auth.send_verification_email_task")
    async def test_logout_clears_cookies_and_blacklists_token(self, mock_email_task, registered_user):
        """AC7: logout blacklists access token and clears cookies."""
        app, _session, email, password, fake_redis = registered_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Login
            login_resp = await ac.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            login_cookies = _parse_set_cookies(login_resp.headers)
            access_tok = login_cookies["access_token"]["value"]
            refresh_tok = login_cookies["refresh_token"]["value"]
            csrf = _csrf_headers(login_resp)

            # Logout
            resp = await ac.post(
                "/api/v1/auth/logout",
                cookies={"access_token": access_tok, "refresh_token": refresh_tok},
                headers=csrf,
            )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Wylogowano pomyślnie"

        # H2: Verify cookies are cleared (max-age=0 or expires in past)
        logout_cookies = _parse_set_cookies(resp.headers)
        assert "access_token" in logout_cookies
        assert "refresh_token" in logout_cookies
        # Cleared cookies have max-age=0
        assert logout_cookies["access_token"].get("max-age") == "0"
        assert logout_cookies["refresh_token"].get("max-age") == "0"

        # Verify access token is blacklisted in Redis
        from app.services.auth.jwt_handler import decode_token

        payload = decode_token(access_tok)
        jti = payload["jti"]
        is_blacklisted = await fake_redis.exists(f"blacklist:{jti}")
        assert is_blacklisted == 1

    async def test_logout_without_tokens_200(self, app):
        """AC7: graceful logout — always returns 200 even without tokens."""
        fake_redis = FakeRedis(decode_responses=True)

        async def override_redis():
            return fake_redis

        app.dependency_overrides[get_redis] = override_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/auth/logout")

        assert resp.status_code == 200
        app.dependency_overrides.clear()
