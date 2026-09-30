"""Testy ApiKeyService — Story 8.6 (AC1, AC2, AC4, AC6; Task 6.1/6.2).

Wzorzec mockowania jak test_notification_service: DB jako AsyncMock,
Redis jako AsyncMock z jawnie ustawianym wynikiem ``set(nx=True)``.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import hash_api_key
from app.models.api_key import ApiKey, ApiKeyScope, ApiKeyStatus
from app.services.auth.api_key_service import (
    KEY_PREFIX,
    ApiKeyService,
    generate_raw_key,
    looks_like_api_key,
)


def _db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _key(**overrides) -> ApiKey:
    raw = overrides.pop("raw", generate_raw_key())
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "key_prefix": raw[:8],
        "key_hash": hash_api_key(raw),
        "name": "CI pipeline",
        "scope": ApiKeyScope.READ_ONLY,
    }
    defaults.update(overrides)
    return ApiKey(**defaults)


# --- format i hash (AC1, Task 6.2) ---


def test_generate_raw_key_ma_prefix_i_64_znaki_hex():
    key = generate_raw_key()
    assert key.startswith(KEY_PREFIX)
    assert len(key) == 68  # "tgn_" + 64
    body = key[len(KEY_PREFIX) :]
    assert len(body) == 64
    int(body, 16)  # sam hex — rzuci ValueError, gdyby było inaczej


def test_generate_raw_key_jest_losowy():
    assert generate_raw_key() != generate_raw_key()


def test_hash_api_key_jest_deterministyczny_i_sha256():
    key = "tgn_" + "a" * 64
    assert hash_api_key(key) == hash_api_key(key)
    assert len(hash_api_key(key)) == 64
    assert hash_api_key(key) != hash_api_key(key + "b")


def test_looks_like_api_key_rozroznia_klucz_od_jwt():
    assert looks_like_api_key(generate_raw_key())
    assert not looks_like_api_key("eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.abc.def")


# --- tworzenie (AC1) ---


@pytest.mark.asyncio
async def test_create_api_key_zwraca_plaintext_i_zapisuje_tylko_hash():
    db = _db()
    service = ApiKeyService(db)
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

    api_key, raw = await service.create_api_key(
        tenant_id=tenant_id,
        user_id=user_id,
        name="CI pipeline",
        scope=ApiKeyScope.FULL_ACCESS,
    )

    assert raw.startswith(KEY_PREFIX)
    assert api_key.key_hash == hash_api_key(raw)
    assert api_key.key_prefix == raw[:8]
    assert raw not in (api_key.key_hash, api_key.key_prefix)
    assert api_key.tenant_id == tenant_id
    assert api_key.user_id == user_id
    assert api_key.scope == ApiKeyScope.FULL_ACCESS
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_api_key_odrzuca_pusta_nazwe():
    service = ApiKeyService(_db())
    with pytest.raises(ValidationError):
        await service.create_api_key(
            tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), name="   ", scope=ApiKeyScope.READ_ONLY
        )


@pytest.mark.asyncio
async def test_create_api_key_odrzuca_nazwe_ponad_100_znakow():
    service = ApiKeyService(_db())
    with pytest.raises(ValidationError):
        await service.create_api_key(
            tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), name="x" * 101, scope=ApiKeyScope.READ_ONLY
        )


@pytest.mark.asyncio
async def test_create_api_key_odrzuca_wygasniecie_w_przeszlosci():
    service = ApiKeyService(_db())
    with pytest.raises(ValidationError):
        await service.create_api_key(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="stary",
            scope=ApiKeyScope.READ_ONLY,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )


@pytest.mark.asyncio
async def test_create_api_key_odrzuca_wygasniecie_ponad_2_lata():
    service = ApiKeyService(_db())
    with pytest.raises(ValidationError):
        await service.create_api_key(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="za daleko",
            scope=ApiKeyScope.READ_ONLY,
            expires_at=datetime.now(UTC) + timedelta(days=731),
        )


@pytest.mark.asyncio
async def test_create_api_key_przyjmuje_naiwna_date_jako_utc():
    db = _db()
    service = ApiKeyService(db)
    naive = (datetime.now(UTC) + timedelta(days=30)).replace(tzinfo=None)

    api_key, _ = await service.create_api_key(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="z datepickera",
        scope=ApiKeyScope.READ_ONLY,
        expires_at=naive,
    )

    assert api_key.expires_at.tzinfo is not None


# --- walidacja (AC2, AC4) ---


@pytest.mark.asyncio
async def test_validate_api_key_znajduje_po_hashu():
    raw = generate_raw_key()
    key = _key(raw=raw)
    db = _db()
    db.execute.return_value = _scalar(key)

    found = await ApiKeyService(db).validate_api_key(raw)

    assert found is key


@pytest.mark.asyncio
async def test_validate_api_key_zwraca_none_dla_tokenu_bez_prefiksu():
    db = _db()
    found = await ApiKeyService(db).validate_api_key("eyJhbGciOiJSUzI1NiJ9.x.y")
    assert found is None
    db.execute.assert_not_called()  # brak zbędnego zapytania dla JWT


@pytest.mark.asyncio
async def test_validate_api_key_zwraca_none_dla_nieznanego_klucza():
    db = _db()
    db.execute.return_value = _scalar(None)
    assert await ApiKeyService(db).validate_api_key(generate_raw_key()) is None


def test_status_wygasly_klucz():
    key = _key(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    assert key.is_expired
    assert not key.is_active
    assert key.status == ApiKeyStatus.EXPIRED


def test_status_odwolany_klucz_ma_pierwszenstwo_przed_wygasnieciem():
    key = _key(
        revoked_at=datetime.now(UTC) - timedelta(days=2),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert key.status == ApiKeyStatus.REVOKED


def test_status_aktywny_klucz_bez_daty_wygasniecia():
    key = _key()
    assert key.is_active
    assert not key.is_expired
    assert key.status == ApiKeyStatus.ACTIVE


def test_is_expired_traktuje_naiwny_timestamp_jako_utc():
    key = _key(expires_at=(datetime.now(UTC) - timedelta(hours=1)).replace(tzinfo=None))
    assert key.is_expired


# --- lista i odwoływanie (AC5) ---


@pytest.mark.asyncio
async def test_list_api_keys_zwraca_klucze_tenanta():
    keys = [_key(), _key()]
    db = _db()
    db.execute.return_value = _scalars(keys)

    assert await ApiKeyService(db).list_api_keys(uuid.uuid4()) == keys


@pytest.mark.asyncio
async def test_revoke_api_key_ustawia_revoked_at():
    key = _key()
    db = _db()
    db.execute.return_value = _scalar(key)

    revoked = await ApiKeyService(db).revoke_api_key(key.id, key.tenant_id)

    assert revoked.revoked_at is not None
    assert revoked.status == ApiKeyStatus.REVOKED


@pytest.mark.asyncio
async def test_revoke_api_key_jest_idempotentne():
    first_revocation = datetime.now(UTC) - timedelta(days=3)
    key = _key(revoked_at=first_revocation)
    db = _db()
    db.execute.return_value = _scalar(key)

    revoked = await ApiKeyService(db).revoke_api_key(key.id, key.tenant_id)

    assert revoked.revoked_at == first_revocation  # nie nadpisujemy pierwszej daty


@pytest.mark.asyncio
async def test_revoke_api_key_nieznany_klucz_to_404():
    db = _db()
    db.execute.return_value = _scalar(None)
    with pytest.raises(NotFoundError):
        await ApiKeyService(db).revoke_api_key(uuid.uuid4(), uuid.uuid4())


# --- dławienie last_used_at (AC6) ---


@pytest.mark.asyncio
async def test_update_last_used_zapisuje_gdy_znacznik_wygasl():
    db = _db()
    redis = AsyncMock()
    redis.set.return_value = True  # NX się udał — brak świeżego znacznika

    assert await ApiKeyService(db, redis=redis).update_last_used(uuid.uuid4()) is True
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_last_used_pomija_zapis_przy_swiezym_znaczniku():
    db = _db()
    redis = AsyncMock()
    redis.set.return_value = None  # klucz w Redisie już jest

    assert await ApiKeyService(db, redis=redis).update_last_used(uuid.uuid4()) is False
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_last_used_zapisuje_gdy_redis_padl():
    db = _db()
    redis = AsyncMock()
    redis.set.side_effect = ConnectionError("redis down")

    assert await ApiKeyService(db, redis=redis).update_last_used(uuid.uuid4()) is True
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_last_used_bez_redisa_zapisuje_zawsze():
    db = _db()
    assert await ApiKeyService(db).update_last_used(uuid.uuid4()) is True
    db.execute.assert_awaited_once()
