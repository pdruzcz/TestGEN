"""Testy klienta tpay /tokens — Story 7.2 (AC2, AC3; Task 2).

Rejestracja tokena (POST /tokens → URL przekierowania), status + wizerunek
(GET /tokens/{value}), usunięcie (DELETE /tokens/{value}). httpx.MockTransport
(wzorzec test_tpay_transactions).
"""

import json
from datetime import date

import httpx
import pytest
from fakeredis import FakeAsyncRedis

from app.services.billing.providers.tpay import TpayProvider
from app.services.billing.providers.tpay.client import TpayApiError
from tests.fixtures.tpay_fixtures import make_test_billing_settings


def _provider(handler) -> TpayProvider:
    redis = FakeAsyncRedis()
    return TpayProvider(
        make_test_billing_settings(),
        redis=redis,
        transport=httpx.MockTransport(handler),
    )


def _oauth(request: httpx.Request) -> httpx.Response | None:
    if request.url.path == "/oauth/auth":
        return httpx.Response(200, json={"access_token": "tok-1", "expires_in": 7200})
    return None


class TestRegisterToken:
    async def test_post_tokens_returns_redirect_url(self):
        """AC2 — POST /tokens z callbackUrl (+cliAuth) → transactionPaymentUrl."""
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            oauth = _oauth(request)
            if oauth:
                return oauth
            if request.method == "POST" and request.url.path == "/tokens":
                seen["body"] = json.loads(request.content.decode())
                return httpx.Response(
                    201,
                    json={
                        "result": "success",
                        "token": "tbe_pending",
                        "transactionPaymentUrl": "https://secure.sandbox.tpay.com/panel/abc",
                    },
                )
            return httpx.Response(404)

        provider = _provider(handler)
        result = await provider.register_card_token(
            callback_url="https://testgen.nexio.pl/billing/payment-methods/return",
            cli_auth="reg-123",
        )

        assert result.transaction_payment_url.startswith("https://")
        assert seen["body"]["callbackUrl"].endswith("/payment-methods/return")
        assert seen["body"]["cliAuth"] == "reg-123"

    async def test_register_error_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            oauth = _oauth(request)
            if oauth:
                return oauth
            return httpx.Response(400, json={"result": "fail", "error": "bad request"})

        provider = _provider(handler)
        with pytest.raises(TpayApiError):
            await provider.register_card_token(callback_url="https://x/callback")


class TestGetToken:
    async def test_get_token_returns_status_and_card_image(self):
        """AC3 — GET /tokens/{value}: status ACTIVE|SUSPENDED|DELETED + wizerunek."""
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            oauth = _oauth(request)
            if oauth:
                return oauth
            if request.method == "GET" and request.url.path == "/tokens/tbe_abc":
                seen["path"] = request.url.path
                return httpx.Response(
                    200,
                    json={
                        "result": "success",
                        "status": "ACTIVE",
                        "cardVendor": "visa",
                        "cardTail": "4242",
                        "expirationDate": "2028-12-31",
                    },
                )
            return httpx.Response(404)

        provider = _provider(handler)
        status = await provider.get_token_status("tbe_abc")

        assert status.status == "ACTIVE"
        assert status.card_tail == "4242"
        assert status.card_brand == "visa"
        assert status.expires_at == date(2028, 12, 31)
        assert seen["path"] == "/tokens/tbe_abc"

    async def test_get_token_missing_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            oauth = _oauth(request)
            if oauth:
                return oauth
            return httpx.Response(404, json={"result": "fail", "error": "not found"})

        provider = _provider(handler)
        with pytest.raises(TpayApiError):
            await provider.get_token_status("tbe_nope")


class TestDeleteToken:
    async def test_delete_token_calls_tpay(self):
        """AC3 — DELETE /tokens/{value} u tpay."""
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            oauth = _oauth(request)
            if oauth:
                return oauth
            if request.method == "DELETE" and request.url.path == "/tokens/tbe_gone":
                seen["method"] = request.method
                return httpx.Response(200, json={"result": "success"})
            return httpx.Response(404)

        provider = _provider(handler)
        await provider.delete_token("tbe_gone")
        assert seen["method"] == "DELETE"

    async def test_delete_error_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            oauth = _oauth(request)
            if oauth:
                return oauth
            return httpx.Response(400, json={"result": "fail", "error": "err"})

        provider = _provider(handler)
        with pytest.raises(TpayApiError):
            await provider.delete_token("tbe_x")
