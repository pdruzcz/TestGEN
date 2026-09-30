"""API testy kluczy API — Story 8.6 (AC1, AC3, AC4, AC5; Task 6.3).

DB mockowana, serwis realny (wzorzec test_notifications). Testy
uwierzytelniania kluczem uderzają w ``authenticate_api_key`` bezpośrednio —
zależność DB/Redis wstrzykiwana mockiem, bez stawiania Postgresa.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from app.core.api_key_auth import authenticate_api_key, extract_api_key
from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import hash_api_key
from app.main import create_app
from app.models.api_key import ApiKey, ApiKeyScope
from app.models.user_tenant import TenantRole
from app.services.auth.api_key_service import generate_raw_key
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _db() -> AsyncMock:
    """DB mock, który — jak prawdziwy flush — dosypuje wartości domyślne.

    ``id`` i ``created_at`` nadaje normalnie SQLAlchemy/Postgres przy zapisie;
    bez tego serializacja odpowiedzi padałaby na ``None`` tylko w teście.
    """
    db = AsyncMock()

    def _add(obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)

    db.add = MagicMock(side_effect=_add)
    return db


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _override_auth(app, user, db, role: str = "owner") -> uuid.UUID:
    from app.core.dependencies import get_current_user, get_db, get_redis

    tenant_id = uuid.uuid4()
    user._tenant_id = tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = role
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    async def override_redis():
        redis = AsyncMock()
        redis.set.return_value = True
        return redis

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    return tenant_id


def _api_key(tenant_id, user_id, *, raw=None, scope=ApiKeyScope.FULL_ACCESS, **overrides) -> ApiKey:
    raw = raw or generate_raw_key()
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "key_prefix": raw[:8],
        "key_hash": hash_api_key(raw),
        "name": "CI pipeline",
        "scope": scope,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ApiKey(**defaults)


# --- POST /api-keys (AC1) ---


@pytest.mark.asyncio
async def test_create_zwraca_201_z_pelnym_kluczem(app, client):
    user = make_user(email="owner@a.com", name="Owner")
    db = _db()
    _override_auth(app, user, db)

    resp = await client.post("/api/v1/api-keys", json={"name": "CI pipeline", "scope": "full_access"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["key"].startswith("tgn_")
    assert len(body["key"]) == 68
    assert body["api_key"]["name"] == "CI pipeline"
    assert body["api_key"]["scope"] == "full_access"
    assert body["api_key"]["status"] == "active"
    assert body["api_key"]["key_prefix"] == body["key"][:8]
    # Hash nie wycieka do odpowiedzi
    assert "key_hash" not in body["api_key"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_domyslny_scope_to_read_only(app, client):
    user = make_user(email="owner@a.com", name="Owner")
    _override_auth(app, user, _db())

    resp = await client.post("/api/v1/api-keys", json={"name": "skrypt"})

    assert resp.status_code == 201
    assert resp.json()["api_key"]["scope"] == "read_only"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_odrzuca_pusta_nazwe(app, client):
    user = make_user(email="owner@a.com", name="Owner")
    _override_auth(app, user, _db())

    resp = await client.post("/api/v1/api-keys", json={"name": ""})

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_wymaga_roli_owner(app, client):
    user = make_user(email="user@a.com", name="User")
    _override_auth(app, user, _db(), role="user")

    resp = await client.post("/api/v1/api-keys", json={"name": "CI"})

    assert resp.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_zapisuje_wpis_audytowy(app, client):
    user = make_user(email="owner@a.com", name="Owner")
    _override_auth(app, user, _db())

    with patch("app.api.routes.api_keys.log_action", new=AsyncMock()) as log:
        resp = await client.post("/api/v1/api-keys", json={"name": "CI"})

    assert resp.status_code == 201
    assert log.await_args.kwargs["action"] == "api_key.created"
    app.dependency_overrides.clear()


# --- GET /api-keys (AC5) ---


@pytest.mark.asyncio
async def test_lista_nie_zawiera_hasha_ani_klucza(app, client):
    user = make_user(email="owner@a.com", name="Owner")
    db = _db()
    tenant_id = _override_auth(app, user, db)
    keys = [
        _api_key(tenant_id, user.id, name="aktywny"),
        _api_key(tenant_id, user.id, name="odwołany", revoked_at=datetime.now(UTC)),
        _api_key(
            tenant_id, user.id, name="wygasły", expires_at=datetime.now(UTC) - timedelta(days=1)
        ),
    ]
    db.execute.return_value = _scalars(keys)

    resp = await client.get("/api/v1/api-keys")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert [k["status"] for k in body["items"]] == ["active", "revoked", "expired"]
    assert all("key_hash" not in k and "key" not in k for k in body["items"])
    app.dependency_overrides.clear()


# --- DELETE /api-keys/{id} (AC5) ---


@pytest.mark.asyncio
async def test_revoke_ustawia_status_revoked(app, client):
    user = make_user(email="owner@a.com", name="Owner")
    db = _db()
    tenant_id = _override_auth(app, user, db)
    key = _api_key(tenant_id, user.id)
    db.execute.return_value = _scalar(key)

    resp = await client.delete(f"/api/v1/api-keys/{key.id}")

    assert resp.status_code == 200
    assert resp.json()["status"] == "revoked"
    assert key.revoked_at is not None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_revoke_nieznanego_klucza_to_404(app, client):
    user = make_user(email="owner@a.com", name="Owner")
    db = _db()
    _override_auth(app, user, db)
    db.execute.return_value = _scalar(None)

    resp = await client.delete(f"/api/v1/api-keys/{uuid.uuid4()}")

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# --- uwierzytelnianie kluczem (AC2, AC3, AC4) ---


def _request(method: str = "GET") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": "/api/v1/projects",
        "headers": [],
        "client": ("10.0.0.1", 1234),
    }
    return Request(scope)


def _auth_db(api_key: ApiKey | None, user=None, role=TenantRole.OWNER) -> AsyncMock:
    """DB oddająca kolejno: SET LOCAL (RLS), klucz, użytkownika, rolę w tenancie."""
    db = _db()
    results = [_scalar(None), _scalar(api_key), _scalar(user), _scalar(role)]
    db.execute.side_effect = lambda *a, **kw: (
        results.pop(0) if results else _scalar(None)
    )
    return db


def test_extract_api_key_rozpoznaje_prefix():
    raw = generate_raw_key()
    assert extract_api_key(f"Bearer {raw}") == raw
    assert extract_api_key("Bearer eyJhbGciOiJSUzI1NiJ9.a.b") is None
    assert extract_api_key(None) is None
    assert extract_api_key("Basic abc") is None


@pytest.mark.asyncio
async def test_auth_kluczem_ustawia_kontekst_tenanta():
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    user.is_active = True
    tenant_id = uuid.uuid4()
    key = _api_key(tenant_id, user.id, raw=raw)
    db = _auth_db(key, user)
    redis = AsyncMock()
    redis.set.return_value = None  # dławienie aktywne — bez zapisu i audytu
    request = _request()

    result = await authenticate_api_key(request, raw, db, redis)

    assert result is user
    assert request.state.tenant_id == tenant_id
    assert request.state.role == "owner"
    assert request.state.is_admin is False
    assert request.state.api_key_id == key.id
    assert user._tenant_id == tenant_id


@pytest.mark.asyncio
async def test_auth_nieznany_klucz_to_401():
    db = _auth_db(None)
    with pytest.raises(AuthError):
        await authenticate_api_key(_request(), generate_raw_key(), db)


@pytest.mark.asyncio
async def test_auth_odwolany_klucz_to_401_z_komunikatem():
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    key = _api_key(uuid.uuid4(), user.id, raw=raw, revoked_at=datetime.now(UTC))
    db = _auth_db(key, user)

    with pytest.raises(AuthError, match="odwołany"):
        await authenticate_api_key(_request(), raw, db)


@pytest.mark.asyncio
async def test_auth_wygasly_klucz_to_401_z_komunikatem():
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    key = _api_key(
        uuid.uuid4(), user.id, raw=raw, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    db = _auth_db(key, user)

    with pytest.raises(AuthError, match="wygasł"):
        await authenticate_api_key(_request(), raw, db)


@pytest.mark.asyncio
async def test_auth_read_only_blokuje_post():
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    key = _api_key(uuid.uuid4(), user.id, raw=raw, scope=ApiKeyScope.READ_ONLY)
    db = _auth_db(key, user)

    with pytest.raises(ForbiddenError, match="read-only"):
        await authenticate_api_key(_request("POST"), raw, db)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
async def test_auth_read_only_przepuszcza_odczyt(method):
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    user.is_active = True
    key = _api_key(uuid.uuid4(), user.id, raw=raw, scope=ApiKeyScope.READ_ONLY)
    db = _auth_db(key, user)
    redis = AsyncMock()
    redis.set.return_value = None

    assert await authenticate_api_key(_request(method), raw, db, redis) is user


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_auth_full_access_przepuszcza_zapis(method):
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    user.is_active = True
    key = _api_key(uuid.uuid4(), user.id, raw=raw, scope=ApiKeyScope.FULL_ACCESS)
    db = _auth_db(key, user)
    redis = AsyncMock()
    redis.set.return_value = None

    assert await authenticate_api_key(_request(method), raw, db, redis) is user


@pytest.mark.asyncio
async def test_auth_zablokowany_wlasciciel_to_401():
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    user.is_blocked = True
    key = _api_key(uuid.uuid4(), user.id, raw=raw)
    db = _auth_db(key, user)

    with pytest.raises(AuthError, match="nieaktywny"):
        await authenticate_api_key(_request(), raw, db)


@pytest.mark.asyncio
async def test_auth_klucz_bez_powiazania_z_tenantem_to_401():
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    user.is_active = True
    key = _api_key(uuid.uuid4(), user.id, raw=raw)
    db = _auth_db(key, user, role=None)

    with pytest.raises(AuthError, match="firmę"):
        await authenticate_api_key(_request(), raw, db)


@pytest.mark.asyncio
async def test_auth_loguje_uzycie_gdy_dlawienie_wygaslo():
    raw = generate_raw_key()
    user = make_user(email="owner@a.com", name="Owner")
    user.is_active = True
    key = _api_key(uuid.uuid4(), user.id, raw=raw)
    db = _auth_db(key, user)
    redis = AsyncMock()
    redis.set.return_value = True  # znacznik wygasł → zapis + audyt

    with patch("app.services.admin.audit_service.log_action", new=AsyncMock()) as log:
        await authenticate_api_key(_request(), raw, db, redis)

    assert log.await_args.kwargs["action"] == "api_key.used"
