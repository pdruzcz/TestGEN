"""Klucze API — generowanie, walidacja, odwoływanie (Story 8.6).

Klucz plaintext istnieje tylko w pamięci procesu, który go wygenerował,
i jest zwracany wywołującemu dokładnie raz (AC1). Wszystkie pozostałe
operacje idą po SHA-256 hashu.

``update_last_used`` jest celowo dławione przez Redis (AC6): CI/CD potrafi
uderzyć setki razy w minutę, a znacznik z dokładnością do 5 minut w zupełności
wystarcza do odpowiedzi na pytanie „czy ten klucz jeszcze żyje". Gdy Redis
jest niedostępny, zapis po prostu się odbywa — dławienie to optymalizacja,
nie warunek poprawności.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import hash_api_key
from app.models.api_key import ApiKey, ApiKeyScope

logger = logging.getLogger(__name__)

KEY_PREFIX = "tgn_"
_KEY_BYTES = 32  # secrets.token_hex(32) = 64 znaki hex
PREFIX_LENGTH = 8  # "tgn_" + 4 hex — identyfikacja klucza na liście
MAX_EXPIRY_DAYS = 730  # 2 lata (AC1)
_LAST_USED_DEBOUNCE_SECONDS = 300  # AC6: max 1 zapis na 5 minut per klucz


def generate_raw_key() -> str:
    """``tgn_`` + 64 znaki hex — 256 bitów losowości z CSPRNG."""
    return f"{KEY_PREFIX}{secrets.token_hex(_KEY_BYTES)}"


def looks_like_api_key(token: str) -> bool:
    """Czy token z nagłówka to klucz API, a nie JWT (rozstrzyga prefix)."""
    return token.startswith(KEY_PREFIX)


class ApiKeyService:
    def __init__(self, db: AsyncSession, redis: Redis | None = None) -> None:
        self.db = db
        self.redis = redis

    async def create_api_key(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        scope: ApiKeyScope,
        expires_at: datetime | None = None,
    ) -> tuple[ApiKey, str]:
        """Tworzy klucz i zwraca ``(rekord, klucz_plaintext)``.

        Plaintext nie trafia do bazy ani do logów — wywołujący ma jedyną
        okazję go pokazać użytkownikowi.
        """
        name = name.strip()
        if not name:
            raise ValidationError("Nazwa klucza jest wymagana")
        if len(name) > 100:
            raise ValidationError("Nazwa klucza może mieć maksymalnie 100 znaków")

        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            now = datetime.now(UTC)
            if expires_at <= now:
                raise ValidationError("Data wygaśnięcia musi być w przyszłości")
            if expires_at > now + timedelta(days=MAX_EXPIRY_DAYS):
                raise ValidationError("Data wygaśnięcia nie może przekraczać 2 lat")

        raw_key = generate_raw_key()
        api_key = ApiKey(
            tenant_id=tenant_id,
            user_id=user_id,
            key_prefix=raw_key[:PREFIX_LENGTH],
            key_hash=hash_api_key(raw_key),
            name=name,
            scope=scope,
            expires_at=expires_at,
        )
        self.db.add(api_key)
        await self.db.flush()
        return api_key, raw_key

    async def validate_api_key(self, raw_key: str) -> ApiKey | None:
        """Zwraca aktywny klucz dla podanego plaintextu albo ``None``.

        Klucz odwołany/wygasły jest zwracany mimo to — rozróżnienie przyczyny
        odmowy (401 „wygasł" vs „odwołany", AC4) robi warstwa wyżej. ``None``
        oznacza wyłącznie „nie ma takiego klucza".
        """
        if not looks_like_api_key(raw_key):
            return None
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw_key))
        )
        return result.scalar_one_or_none()

    async def list_api_keys(self, tenant_id: uuid.UUID) -> list[ApiKey]:
        """Wszystkie klucze tenanta — także odwołane i wygasłe (AC5)."""
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.tenant_id == tenant_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_api_key(self, key_id: uuid.UUID, tenant_id: uuid.UUID) -> ApiKey:
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == tenant_id)
        )
        api_key = result.scalar_one_or_none()
        if api_key is None:
            raise NotFoundError("Klucz API nie został znaleziony")
        return api_key

    async def revoke_api_key(self, key_id: uuid.UUID, tenant_id: uuid.UUID) -> ApiKey:
        """Soft delete — ``revoked_at`` zamiast usunięcia (AC5, ślad w audycie)."""
        api_key = await self.get_api_key(key_id, tenant_id)
        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(UTC)
            await self.db.flush()
        return api_key

    async def update_last_used(self, key_id: uuid.UUID) -> bool:
        """Zapisuje ``last_used_at``, nie częściej niż raz na 5 minut (AC6).

        Zwraca ``True``, gdy zapis faktycznie poszedł do bazy.
        """
        if self.redis is not None:
            try:
                fresh = await self.redis.set(
                    f"api_key:{key_id}:last_used",
                    datetime.now(UTC).isoformat(),
                    ex=_LAST_USED_DEBOUNCE_SECONDS,
                    nx=True,
                )
            except Exception:  # Redis padł — zapisujemy bez dławienia
                logger.warning("Redis niedostępny przy dławieniu last_used_at", exc_info=True)
            else:
                if not fresh:  # znacznik świeży — pomijamy zapis
                    return False

        await self.db.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(last_used_at=datetime.now(UTC))
        )
        return True
