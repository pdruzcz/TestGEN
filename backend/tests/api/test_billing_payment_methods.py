"""Testy API metód płatności — Story 7.2 (AC2, AC3; Task 8.4).

GET/POST/DELETE /billing/payment-methods — guardy roli Owner, rejestracja
bez obciążenia (URL przekierowania), 409 na ostatnią metodę przy aktywnej
subskrypcji cyklicznej, 502 na błąd tpay. DB mockowana + provider mock
(wzorzec test_billing_checkout).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db, get_payment_provider
from app.main import create_app
from app.models.payment import PaymentToken, TokenKind, TpayTokenStatus
from app.services.billing.subscription_service import encrypt_token_value, token_digest
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, role="owner"):
    from fastapi import Request

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

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return tenant_id


def _override_provider(app) -> AsyncMock:
    provider = AsyncMock()
    app.dependency_overrides[get_payment_provider] = lambda: provider
    return provider


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _token(tenant_id, status=TpayTokenStatus.ACTIVE, **kw) -> PaymentToken:
    fields = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind=TokenKind.CARD_TOKEN,
        value_encrypted=encrypt_token_value(tenant_id, "tbe_x"),
        value_digest=token_digest(tenant_id, "tbe_x"),
        tpay_status=status,
        card_tail="4242",
        card_brand="visa",
        is_default=False,  # po flush w DB default FALSE; w pamięci jawne
        created_at=datetime.now(UTC),
    )
    fields.update(kw)
    return PaymentToken(**fields)


class TestListPaymentMethods:
    async def test_owner_gets_list(self, client, app):
        from app.services.billing.providers.base import ProviderTokenStatus

        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        provider = _override_provider(app)
        # 7.7 Task 1.1: GET wzbogaca stan kart o GET /tokens/{value} u tpay.
        provider.get_token_status = AsyncMock(
            return_value=ProviderTokenStatus(status="ACTIVE", card_tail="4242", card_brand="visa")
        )
        db.execute = AsyncMock(side_effect=[_scalars([_token(tid)])])

        resp = await client.get("/api/v1/billing/payment-methods")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["kind"] == "card_token"
        assert body[0]["card_tail"] == "4242"
        assert body[0]["tpay_status"] == "active"
        assert body[0]["is_default"] is False

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        resp = await client.get("/api/v1/billing/payment-methods")
        assert resp.status_code == 403


class TestRegisterPaymentMethod:
    async def test_post_returns_registration_url(self, client, app):
        """AC2 — rejestracja: rekord PENDING + URL przekierowania od tpay."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        provider = _override_provider(app)
        from app.services.billing.providers.base import TokenRegistrationResult

        provider.register_card_token = AsyncMock(
            return_value=TokenRegistrationResult(transaction_payment_url="https://secure.tpay.com/panel/reg")
        )
        pending_holder: dict = {}

        async def fake_execute(*a, **kw):
            pending_holder["calls"] = pending_holder.get("calls", 0) + 1
            return _scalar(None)  # brak subskrypcji (link pomija)

        db.execute = AsyncMock(side_effect=fake_execute)

        resp = await client.post("/api/v1/billing/payment-methods")

        assert resp.status_code == 200
        body = resp.json()
        assert body["registration_url"].startswith("https://")
        assert body["token_id"]
        # cliAuth = registration_id przekazany do tpay (korelacja data.token)
        _, kwargs = provider.register_card_token.call_args
        assert kwargs.get("cli_auth")
        assert "payment-methods/return" in kwargs.get("callback_url", "")

    async def test_post_provider_error_rolls_back(self, client, app):
        """tpay niedostępny → 502, bez pozostawiania rekordu PENDING."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        provider = _override_provider(app)
        provider.register_card_token = AsyncMock(side_effect=RuntimeError("tpay down"))
        db.execute = AsyncMock(side_effect=[_scalar(None)])

        resp = await client.post("/api/v1/billing/payment-methods")
        assert resp.status_code == 502
        db.rollback.assert_awaited_once()

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        resp = await client.post("/api/v1/billing/payment-methods")
        assert resp.status_code == 403


class TestPaymentMethodsEnrichment:
    """Story 7.7 Task 1.1 — GET /payment-methods wzbogacany o stan z GET /tokens/{value}.

    Wizerunek karty (brand/ogon/status) odświeżany u tpay z krótkoterminowym
    cache'em; błąd dostawcy → graceful degrade do stanu lokalnego. Aliasy BLIK
    i rejestracje pending nie podlegają odpytaniu /tokens.
    """

    @pytest.fixture(autouse=True)
    def _clear_token_status_cache(self):
        from app.services.billing import subscription_service as subscription_service_module

        subscription_service_module._token_status_cache.clear()
        yield
        subscription_service_module._token_status_cache.clear()

    async def test_get_enriches_card_status_from_tpay(self, client, app):
        from app.services.billing.providers.base import ProviderTokenStatus

        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        provider = _override_provider(app)
        provider.get_token_status = AsyncMock(
            return_value=ProviderTokenStatus(status="SUSPENDED", card_tail="1111", card_brand="mastercard")
        )
        token = _token(tid)  # lokalnie: active / visa / 4242
        db.execute = AsyncMock(side_effect=[_scalars([token])])

        resp = await client.get("/api/v1/billing/payment-methods")

        assert resp.status_code == 200
        provider.get_token_status.assert_awaited_once_with("tbe_x")
        body = resp.json()
        assert body[0]["tpay_status"] == "suspended"
        assert body[0]["card_brand"] == "mastercard"
        assert body[0]["card_tail"] == "1111"
        db.commit.assert_awaited_once()  # dryf zapisany lokalnie

    async def test_enrichment_uses_short_term_cache(self, client, app):
        from app.services.billing.providers.base import ProviderTokenStatus

        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        provider = _override_provider(app)
        provider.get_token_status = AsyncMock(
            return_value=ProviderTokenStatus(status="ACTIVE", card_tail="4242", card_brand="visa")
        )
        token = _token(tid)  # ten sam identyfikator w obu przebiegach (klucz cache)
        db.execute = AsyncMock(side_effect=[_scalars([token]), _scalars([token])])

        await client.get("/api/v1/billing/payment-methods")
        await client.get("/api/v1/billing/payment-methods")

        provider.get_token_status.assert_awaited_once()  # drugi GET z cache

    async def test_tpay_error_returns_local_state(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        provider = _override_provider(app)
        provider.get_token_status = AsyncMock(side_effect=RuntimeError("tpay down"))
        db.execute = AsyncMock(side_effect=[_scalars([_token(tid)])])

        resp = await client.get("/api/v1/billing/payment-methods")

        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["tpay_status"] == "active"
        assert body[0]["card_brand"] == "visa"
        assert body[0]["card_tail"] == "4242"

    async def test_blik_alias_and_pending_not_enriched(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        provider = _override_provider(app)
        alias = _token(tid, kind=TokenKind.BLIK_ALIAS_PAYID, card_tail=None, card_brand=None)
        pending = _token(tid, status=TpayTokenStatus.PENDING, value_encrypted=None, value_digest=None)
        db.execute = AsyncMock(side_effect=[_scalars([alias, pending])])

        resp = await client.get("/api/v1/billing/payment-methods")

        assert resp.status_code == 200
        provider.get_token_status.assert_not_awaited()


class TestDeletePaymentMethod:
    def _sub_row(self, tenant_id, token_id, recurring=True):
        from app.models.subscription import Subscription, SubscriptionStatus

        now = datetime.now(UTC)
        return Subscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            plan_id=uuid.uuid4(),
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_charge_at=now + timedelta(days=30) if recurring else None,
            cancel_at_period_end=not recurring,
            payment_token_id=token_id,
        )

    async def test_delete_calls_tpay_and_soft_deletes(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        provider = _override_provider(app)
        token = _token(tid)
        db.execute = AsyncMock(side_effect=[_scalar(token), _scalars([]), _scalar(None)])

        resp = await client.delete(f"/api/v1/billing/payment-methods/{token.id}")

        assert resp.status_code == 200
        provider.delete_token.assert_awaited_once_with("tbe_x")
        assert resp.json()["tpay_status"] == "deleted"

    async def test_delete_last_method_with_recurring_subscription_409(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        _override_provider(app)
        token = _token(tid)
        db.execute = AsyncMock(side_effect=[_scalar(token), _scalars([]), _scalar(self._sub_row(tid, token.id))])

        resp = await client.delete(f"/api/v1/billing/payment-methods/{token.id}")
        assert resp.status_code == 409
        assert "najpierw dodaj" in resp.json()["detail"].lower() or "metod" in resp.json()["detail"]

    async def test_delete_not_found_404(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        _override_provider(app)
        db.execute = AsyncMock(side_effect=[_scalar(None)])

        resp = await client.delete(f"/api/v1/billing/payment-methods/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        resp = await client.delete(f"/api/v1/billing/payment-methods/{uuid.uuid4()}")
        assert resp.status_code == 403
