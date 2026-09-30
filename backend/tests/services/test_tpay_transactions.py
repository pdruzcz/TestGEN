"""Testy klienta tpay — OAuth cache, create/get transaction (Story 7.4 AC1/AC7/AC8).

httpx.MockTransport zamiast realnych połączeń; fakeredis jako cache Bearer
tokena (TTL 2 h, odnawianie po wygaśnięciu).
"""

import json
from decimal import Decimal

import httpx
import pytest
from fakeredis import FakeAsyncRedis

from app.services.billing.providers.base import CheckoutResult, ProviderTransaction
from app.services.billing.providers.tpay import TpayProvider
from app.services.billing.providers.tpay.auth import TpayAuthClient, TpayAuthError
from app.services.billing.providers.tpay.client import TpayApiError, TpayClient
from app.services.billing.providers.tpay.transactions import is_paid
from tests.fixtures.tpay_fixtures import make_test_billing_settings


def _transport_log(handler):
    """MockTransport zapisujący żądania (do asercji payloadów)."""
    log: list[httpx.Request] = []
    inner = httpx.MockTransport(handler)

    async def router(request: httpx.Request) -> httpx.Response:
        log.append(request)
        return await inner.handle_async_request(request)  # type: ignore[arg-type]

    return httpx.MockTransport(router), log


def _oauth_ok(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/oauth/auth":
        return httpx.Response(200, json={"access_token": "tok-1", "expires_in": 7200, "token_type": "bearer"})
    return httpx.Response(404)


class TestOAuth:
    async def test_token_fetched_and_cached_in_redis(self):
        """AC8: Bearer z client_credentials, cache w Redis z TTL 2 h."""
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.url.path == "/oauth/auth":
                assert "client_id" in request.content.decode()
                return httpx.Response(200, json={"access_token": "tok-1", "expires_in": 7200})
            return httpx.Response(404)

        redis = FakeAsyncRedis()
        auth = TpayAuthClient(make_test_billing_settings(), redis=redis, transport=httpx.MockTransport(handler))

        t1 = await auth.get_access_token()
        t2 = await auth.get_access_token()  # z cache — bez drugiego POST /oauth/auth

        assert t1 == t2 == "tok-1"
        assert len(calls) == 1
        ttl = await redis.ttl("billing:tpay:oauth_token")
        assert 0 < ttl <= 7200  # odnowienie przed wygaśnięciem (zapas 60 s)
        await redis.aclose()

    async def test_token_ttl_capped_at_2h(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"access_token": "tok-2", "expires_in": 99999})

        redis = FakeAsyncRedis()
        auth = TpayAuthClient(make_test_billing_settings(), redis=redis, transport=httpx.MockTransport(handler))
        await auth.get_access_token()
        ttl = await redis.ttl("billing:tpay:oauth_token")
        assert ttl <= 7200
        await redis.aclose()

    async def test_missing_credentials_raise(self):
        auth = TpayAuthClient(make_test_billing_settings(tpay_client_id=""))
        with pytest.raises(TpayAuthError, match="not configured"):
            await auth.get_access_token()

    async def test_oauth_failure_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid_client"})

        auth = TpayAuthClient(make_test_billing_settings(), transport=httpx.MockTransport(handler))
        with pytest.raises(TpayAuthError, match="401"):
            await auth.get_access_token()


class TestClient:
    async def test_post_bearer_and_result_check(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/auth":
                return httpx.Response(200, json={"access_token": "tok-1", "expires_in": 7200})
            assert request.headers["Authorization"] == "Bearer tok-1"
            if request.url.path == "/transactions":
                return httpx.Response(
                    200,
                    json={"result": "success", "transactionId": "ta_X", "transactionPaymentUrl": "https://pay"},
                )
            return httpx.Response(404)

        settings = make_test_billing_settings()
        client = TpayClient(settings, transport=httpx.MockTransport(handler))
        data = await client.post("/transactions", json={"amount": 30.0})
        assert data["transactionId"] == "ta_X"

    async def test_provider_result_error_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/auth":
                return httpx.Response(200, json={"access_token": "tok-1", "expires_in": 7200})
            return httpx.Response(200, json={"result": "error", "error": "invalid amount"})

        client = TpayClient(make_test_billing_settings(), transport=httpx.MockTransport(handler))
        with pytest.raises(TpayApiError, match="invalid amount"):
            await client.post("/transactions", json={})

    async def test_http_error_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/auth":
                return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
            return httpx.Response(500, text="boom")

        client = TpayClient(make_test_billing_settings(), transport=httpx.MockTransport(handler))
        with pytest.raises(TpayApiError, match="500"):
            await client.get("/transactions/ta_X")


class TestCreateTransaction:
    async def test_create_transaction_payload_and_result(self):
        """AC1: amount, payer, hiddenDescription=order_id, callbacki, pay.groupId."""
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/auth":
                return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
            seen["path"] = request.url.path
            seen["payload"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "result": "success",
                    "transactionId": "ta_bKvkJX9Knk9Ol4od",
                    "transactionPaymentUrl": "https://sandbox.tpay.com/...",
                },
            )

        settings = make_test_billing_settings()
        provider = TpayProvider(settings, transport=httpx.MockTransport(handler))
        result = await provider.create_checkout(
            amount=Decimal("30.00"),
            currency="PLN",
            description="TestGEN — subskrypcja Basic (miesięczna)",
            order_id="ord-123",
            payer_email="owner@test.com",
            payer_name="Jan Owner",
            group_id="150",
        )

        assert isinstance(result, CheckoutResult)
        assert result.transaction_id == "ta_bKvkJX9Knk9Ol4od"
        assert result.transaction_payment_url.startswith("https://")
        payload = seen["payload"]
        assert seen["path"] == "/transactions"
        assert payload["amount"] == 30.0
        assert payload["hiddenDescription"] == "ord-123"
        assert payload["payer"] == {"email": "owner@test.com", "name": "Jan Owner"}
        assert payload["callbacks"]["notification"]["url"] == settings.tpay_notification_url
        assert payload["callbacks"]["payerUrls"] == {
            "success": settings.tpay_success_url,
            "error": settings.tpay_error_url,
        }
        assert payload["pay"] == {"groupId": 150}

    async def test_create_transaction_without_group(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/auth":
                return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
            return httpx.Response(
                200,
                json={"result": "success", "transactionId": "ta_1", "transactionPaymentUrl": "https://x"},
            )

        provider = TpayProvider(make_test_billing_settings(), transport=httpx.MockTransport(handler))
        result = await provider.create_checkout(
            amount=Decimal("50.00"),
            currency="PLN",
            description="d",
            order_id="ord-2",
            payer_email="a@b.c",
        )
        assert result.transaction_id == "ta_1"


class TestGetTransaction:
    async def test_get_transaction_maps_response(self):
        """AC7: fallback reconciliation — mapowanie statusu/kwot."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/auth":
                return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
            assert request.url.path == "/transactions/ta_X"
            assert request.method == "GET"
            return httpx.Response(
                200,
                json={
                    "result": "success",
                    "transactionId": "ta_X",
                    "status": "paid",
                    "amount": 30.0,
                    "paidAmount": 30.0,
                    "testMode": True,
                },
            )

        provider = TpayProvider(make_test_billing_settings(), transport=httpx.MockTransport(handler))
        remote = await provider.get_transaction("ta_X")
        assert isinstance(remote, ProviderTransaction)
        assert remote.status == "paid"
        assert is_paid(remote.status) is True
        assert remote.amount == Decimal("30.0")
        assert remote.test_mode is True

    async def test_get_transaction_without_paid_amount(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/auth":
                return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
            return httpx.Response(200, json={"result": "success", "status": "pending", "amount": 30.0})

        provider = TpayProvider(make_test_billing_settings(), transport=httpx.MockTransport(handler))
        remote = await provider.get_transaction("ta_X")
        assert remote.paid_amount is None
        assert is_paid(remote.status) is False


class TestBlikAliasRegistration:
    """Story 7.2 AC4/AC7 — rejestracja aliasu BLIK (PAYID) przy checkoucie."""

    async def test_create_transaction_includes_alias_and_autopayment_a(self):
        """AC4: blikPaymentData.aliases.* + autopayment.model = A (stała kwota)."""
        import json as _json

        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/auth":
                return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
            if request.method == "POST" and request.url.path == "/transactions":
                seen["body"] = _json.loads(request.content.decode())
                return httpx.Response(
                    200,
                    json={"result": "success", "transactionId": "ta_B", "transactionPaymentUrl": "https://p"},
                )
            return httpx.Response(404)

        provider = TpayProvider(make_test_billing_settings(), transport=httpx.MockTransport(handler))
        await provider.create_checkout(
            amount=Decimal("30.00"),
            currency="PLN",
            description="TestGEN — subskrypcja",
            order_id="ord-1",
            payer_email="a@b.pl",
        )

        alias = seen["body"]["blikPaymentData"]["aliases"][0]
        # Ograniczenia wg konfiguracji planu: kwota subskrypcji jako limit pojedynczy.
        assert alias["singleLimitAmount"] == 30.00
        assert alias["totalLimitAmount"] == 360.00  # 12 x cena (konfiguracja)
        assert alias["frequency"] == "eachMonth"
        assert alias["initDate"]
        assert alias["expirationDate"]
        # AC7: model O poza v1 — wyłącznie model A (stała kwota).
        assert seen["body"]["autopayment"] == {"model": "A"}

    async def test_alias_limits_from_settings(self):
        """Limity pochodzą z konfiguracji (nie hardcode) — env wymienne."""

        from app.services.billing.providers.tpay.transactions import build_blik_alias_registration

        settings = make_test_billing_settings(
            tpay_blik_alias_frequency="eachWeek",
            tpay_blik_alias_total_limit_payments=6,
            tpay_blik_alias_expiration_days=180,
        )
        alias = build_blik_alias_registration(Decimal("50.00"), settings)
        assert alias["frequency"] == "eachWeek"
        assert alias["singleLimitAmount"] == 50.00
        assert alias["totalLimitAmount"] == 300.00
        assert alias["expirationDate"] > alias["initDate"]
