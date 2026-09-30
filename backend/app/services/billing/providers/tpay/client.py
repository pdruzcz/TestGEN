"""Generyczny klient HTTP tpay Open API (Story 7.4, Task 2.3).

Niskopoziomowe ``post``/``get`` z Bearerem z ``auth.py``. Typowane
wrappery dla konkretnych zasobów żyją obok: ``transactions.py`` (7.4),
``/refunds``/``/tokens``/``/blik/alias`` dokładają Stories 7.2/7.3/7.5 —
korzystają z tych samych metod.
"""

import logging
from typing import Any

import httpx
from redis.asyncio import Redis

from app.core.config_billing import BillingSettings
from app.services.billing.providers.tpay.auth import TpayAuthClient

logger = logging.getLogger(__name__)


class TpayApiError(RuntimeError):
    """Błąd API tpay (non-2xx albo brak ``result: success``)."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(f"tpay API error {status_code}: {detail[:300]}")


class TpayClient:
    def __init__(
        self,
        settings: BillingSettings,
        redis: Redis | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._auth = TpayAuthClient(settings, redis=redis, transport=transport)
        self._transport = transport

    async def post(self, path: str, json: dict) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def get(self, path: str) -> dict[str, Any]:
        return await self._request("GET", path)

    async def delete(self, path: str) -> dict[str, Any]:
        return await self._request("DELETE", path)

    async def _request(self, method: str, path: str, *, json: dict | None = None) -> dict[str, Any]:
        token = await self._auth.get_access_token()
        url = f"{self._settings.api_base_url}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                transport=self._transport,
                headers={"Authorization": f"Bearer {token}"},
            ) as http:
                resp = await http.request(method, url, json=json)
        except httpx.HTTPError as exc:
            raise TpayApiError(0, f"request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise TpayApiError(resp.status_code, resp.text)
        data = resp.json()
        # tpay zaznacza sukces przez "result": "success" (wyjątkiem jest OAuth)
        if isinstance(data, dict) and data.get("result") not in (None, "success"):
            raise TpayApiError(resp.status_code, str(data.get("error", data)))
        return data
