"""Unit tests for JWT RS256 token creation and decoding."""

import uuid
from datetime import UTC

import jwt
import pytest

from app.services.auth.jwt_handler import (
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
)


@pytest.fixture()
def user_id():
    return uuid.uuid4()


@pytest.fixture()
def tenant_id():
    return uuid.uuid4()


class TestCreateAccessToken:
    def test_creates_valid_jwt(self, user_id, tenant_id):
        token = create_access_token(user_id, tenant_id, "owner")
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["role"] == "owner"
        assert payload["type"] == "access"
        assert payload["iss"] == "testgen"
        assert payload["aud"] == "testgen"

    def test_contains_exp_and_iat(self, user_id, tenant_id):
        token = create_access_token(user_id, tenant_id, "user")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]

    def test_access_token_has_jti(self, user_id, tenant_id):
        token = create_access_token(user_id, tenant_id, "user")
        payload = decode_token(token)
        assert "jti" in payload

    def test_access_tokens_have_unique_jti(self, user_id, tenant_id):
        t1 = create_access_token(user_id, tenant_id, "user")
        t2 = create_access_token(user_id, tenant_id, "user")
        assert decode_token(t1)["jti"] != decode_token(t2)["jti"]


class TestCreateRefreshToken:
    def test_creates_valid_refresh_token(self, user_id):
        token = create_refresh_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "jti" in payload

    def test_refresh_tokens_have_unique_jti(self, user_id):
        t1 = create_refresh_token(user_id)
        t2 = create_refresh_token(user_id)
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        assert p1["jti"] != p2["jti"]


class TestCreateMfaToken:
    def test_creates_valid_mfa_token(self, user_id):
        token = create_mfa_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "mfa"
        assert "jti" in payload


class TestDecodeToken:
    def test_decode_valid_token(self, user_id, tenant_id):
        token = create_access_token(user_id, tenant_id, "admin")
        payload = decode_token(token)
        assert payload["role"] == "admin"

    def test_decode_expired_token_raises(self, user_id, tenant_id):
        from datetime import datetime, timedelta

        from app.core.config import get_settings

        settings = get_settings()
        private_key = settings.jwt_private_key_path.read_text()
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": "user",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
            "type": "access",
            "iss": "testgen",
            "aud": "testgen",
        }
        token = jwt.encode(payload, private_key, algorithm="RS256")
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token)

    def test_decode_tampered_token_raises(self, user_id, tenant_id):
        token = create_access_token(user_id, tenant_id, "user")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(tampered)

    def test_decode_wrong_issuer_raises(self, user_id, tenant_id):
        """JWT with wrong issuer must be rejected."""
        from datetime import datetime, timedelta

        from app.core.config import get_settings

        settings = get_settings()
        private_key = settings.jwt_private_key_path.read_text()
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": "user",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "type": "access",
            "iss": "wrong-issuer",
            "aud": "testgen",
        }
        token = jwt.encode(payload, private_key, algorithm="RS256")
        with pytest.raises(jwt.InvalidIssuerError):
            decode_token(token)

    def test_decode_wrong_audience_raises(self, user_id, tenant_id):
        """JWT with wrong audience must be rejected."""
        from datetime import datetime, timedelta

        from app.core.config import get_settings

        settings = get_settings()
        private_key = settings.jwt_private_key_path.read_text()
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": "user",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "type": "access",
            "iss": "testgen",
            "aud": "wrong-audience",
        }
        token = jwt.encode(payload, private_key, algorithm="RS256")
        with pytest.raises(jwt.InvalidAudienceError):
            decode_token(token)

    def test_hs256_algorithm_confusion_rejected(self, user_id, tenant_id):
        """M17: HS256 token must be rejected — only RS256 is accepted."""
        from datetime import datetime, timedelta

        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": "admin",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "type": "access",
            "iss": "testgen",
            "aud": "testgen",
        }
        # Sign with HS256 using arbitrary secret — must be rejected by decode_token
        token = jwt.encode(payload, "some-secret-key", algorithm="HS256")
        with pytest.raises((jwt.InvalidAlgorithmError, jwt.InvalidSignatureError, jwt.InvalidTokenError)):
            decode_token(token)
