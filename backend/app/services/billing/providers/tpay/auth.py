"""tpay OAuth2 client_credentials — Bearer do Open API (Story 7.4, AC8).

Token cache'owany w Redisie (TTL = ``expires_in`` minus zapas 60 s, maks. 2 h)
i odnawiany po wygaśnięciu. Bez Redisa (np. testy) token jest po prostu
pobierany przy każdym żądaniu.
"""

import logging

import httpx
from redis.asyncio import Redis

from app.core.config_billing import BillingSettings

logger = logging.getLogger(__name__)

_TOKEN_REDIS_KEY = "billing:tpay:oauth_token"
_TOKEN_TTL_CAP = 7200  # 2 h — górne ograniczenie TTL (AC8)
_TOKEN_TTL_SAFETY = 60  # sekund zapasu przed wygaśnięciem


class TpayAuthError(RuntimeError):
    """Nieudane uwierzytelnienie OAuth2 tpay."""


class TpayAuthClient:
    def __init__(
        self,
        settings: BillingSettings,
        redis: Redis | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._redis = redis
        self._transport = transport

    async def get_access_token(self) -> str:
        """Bearer token — z cache (Redis) albo świeży POST /oauth/auth."""
        if self._redis is not None:
            cached = await self._redis.get(_TOKEN_REDIS_KEY)
            if cached:
                return cached if isinstance(cached, str) else cached.decode()

        if not self._settings.tpay_client_id or not self._settings.tpay_client_secret.get_secret_value():
            raise TpayAuthError("tpay OAuth not configured — set TPAY_CLIENT_ID / TPAY_CLIENT_SECRET (env only)")

        token, expires_in = await self._fetch_token()
        ttl = min(expires_in - _TOKEN_TTL_SAFETY, _TOKEN_TTL_CAP)
        if self._redis is not None and ttl > 0:
            await self._redis.set(_TOKEN_REDIS_KEY, token, ex=ttl)
        return token

    async def _fetch_token(self) -> tuple[str, int]:
        url = f"{self._settings.api_base_url}/oauth/auth"
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                transport=self._transport,
            ) as http:
                resp = await http.post(
                    url,
                    json={
                        "client_id": self._settings.tpay_client_id,
                        "client_secret": self._settings.tpay_client_secret.get_secret_value(),
                    },
                )
        except httpx.HTTPError as exc:
            raise TpayAuthError(f"tpay OAuth request failed: {exc}") from exc
        if resp.status_code != 200:
            raise TpayAuthError(f"tpay OAuth error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise TpayAuthError("tpay OAuth response missing access_token")
        return token, int(data.get("expires_in", 7200))
