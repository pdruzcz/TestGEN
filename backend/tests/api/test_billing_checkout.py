"""Testy API checkoutu i webhooka tpay — Story 7.4 (AC1, AC3, AC4, AC7).

POST /billing/checkout — guardy 403 (rola) / 409 (aktywny plan płatny),
rekord pending z hidden_description=order_id (korelacja tr_crc).
POST /billing/webhooks/tpay — kontrakt TRUE/400, korelacja po hidden_description.
DB mockowana (wzorzec test_billing_plans); provider z certyfikatem testowym.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db, get_payment_provider
from app.main import create_app
from app.models.payment import PaymentStatus, PaymentTransaction, WebhookProcessingStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.services.billing.providers.base import CheckoutResult
from app.services.billing.providers.tpay import TpayProvider
from tests.factories import make_user
from tests.fixtures.billing_fixtures import savepoint_cm
from tests.fixtures.tpay_fixtures import (
    build_notification,
    make_test_billing_settings,
    sign_jws,
    signing_cert_pem,
)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, tenant_id=None, role="user", with_tenant=True):
    from fastapi import Request

    _tenant_id = tenant_id or uuid.uuid4()
    if with_tenant:
        user._tenant_id = _tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = _tenant_id
        request.state.role = role
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _override_provider(app) -> TpayProvider:
    provider = TpayProvider(make_test_billing_settings(), pinned_cert_pem=signing_cert_pem())
    app.dependency_overrides[get_payment_provider] = lambda: provider
    return provider


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _sub(plan: SubscriptionPlan, status=SubscriptionStatus.ACTIVE) -> Subscription:
    return Subscription(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        plan_id=plan.id,
        status=status,
        current_period_start=datetime.now(UTC),
        current_period_end=datetime.now(UTC) + timedelta(days=30),
        cancel_at_period_end=False,
    )


class TestCheckoutGuards:
    """AC1 — guardy roli i aktywnego planu płatnego."""

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")  # zwykły User tenanta
        _override_provider(app)

        resp = await client.post("/api/v1/billing/checkout", json={"plan": "basic"})

        assert resp.status_code == 403

    async def test_admin_role_bypasses_owner_check(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="owner", with_tenant=False)

        from fastapi import Request

        async def override_user(request: Request):
            request.state.user = user
            request.state.tenant_id = None
            request.state.role = "owner"
            request.state.is_admin = True  # admin bypass
            return user

        app.dependency_overrides[get_current_user] = override_user

        # brak tenantu → 403 z _tenant_of (admin bez kontekstu tenanta)
        resp = await client.post("/api/v1/billing/checkout", json={"plan": "basic"})
        assert resp.status_code == 403

    async def test_active_paid_plan_gets_409(self, client, app):
        """AC1: tenant z aktywnym Basic/Premium → 409 (zmiana planu: 7.5)."""
        user = make_user()
        basic = SubscriptionPlan(id=uuid.uuid4(), name=PlanName.BASIC, display_name="Basic")
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(_sub(basic)), _scalar(basic)])

        _override_auth(app, user, db, role="owner")
        _override_provider(app)

        resp = await client.post("/api/v1/billing/checkout", json={"plan": "premium"})

        assert resp.status_code == 409
        assert "subscription/change" in resp.json()["detail"]

    async def test_freemium_active_can_checkout(self, client, app):
        """AC1: Freemium może kupić każdy plan płatny."""
        user = make_user()
        freemium = SubscriptionPlan(id=uuid.uuid4(), name=PlanName.FREEMIUM, display_name="Freemium")
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(_sub(freemium)), _scalar(freemium), _scalar(None)])

        _override_auth(app, user, db, role="owner")
        provider = _override_provider(app)
        provider.create_checkout = AsyncMock(
            return_value=CheckoutResult(transaction_id="ta_1", transaction_payment_url="https://tpay/pay")
        )

        resp = await client.post("/api/v1/billing/checkout", json={"plan": "basic"})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["transaction_id"] == "ta_1"
        assert body["transaction_payment_url"] == "https://tpay/pay"
        assert body["amount"] == "30.00"
        # rekord pending z hidden_description = order_id (UUID — korelacja tr_crc)
        added = db.add.call_args.args[0]
        assert isinstance(added, PaymentTransaction)
        assert added.status == PaymentStatus.PENDING
        uuid.UUID(added.hidden_description)  # poprawny UUID
        assert added.meta["plan"] == "basic"
        assert added.transaction_id == "ta_1"
        db.commit.assert_awaited()

    async def test_provider_failure_rolls_back_and_502(self, client, app):
        user = make_user()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(None)])

        _override_auth(app, user, db, role="owner")
        provider = _override_provider(app)
        provider.create_checkout = AsyncMock(side_effect=RuntimeError("tpay down"))

        resp = await client.post("/api/v1/billing/checkout", json={"plan": "basic"})

        assert resp.status_code == 502
        db.rollback.assert_awaited()

    async def test_invalid_plan_rejected_422(self, client, app):
        user = make_user()
        _override_auth(app, user, AsyncMock(), role="owner")
        _override_provider(app)

        resp = await client.post("/api/v1/billing/checkout", json={"plan": "freemium"})
        assert resp.status_code == 422  # Literal["basic","premium"] — Freemium nie podlega zakupowi


class TestWebhookEndpoint:
    """AC3/AC4 — kontrakt HTTP webhooka + korelacja (AC5)."""

    async def test_valid_notification_answers_true_literal(self, client, app):
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            hidden_description="ord-1",
            amount=Decimal("30.00"),
            currency="PLN",
            status=PaymentStatus.PENDING,
            meta={"plan": "basic"},
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL RLS
                _scalar(None),  # dedup
                _scalar(txn),  # korelacja po hidden_description == tr_crc
                _scalar(SubscriptionPlan(id=uuid.uuid4(), name=PlanName.BASIC, display_name="Basic")),
                _scalar(None),  # subskrypcja: nowa
                MagicMock(),  # UPDATE tenants.plan
            ]
        )
        _override_auth(app, make_user(), db, role="owner")
        _override_provider(app)

        body = build_notification(tr_crc="ord-1")
        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "X-JWS-Signature": sign_jws(body)},
        )

        assert resp.status_code == 200
        assert resp.text == "TRUE"  # dosłownie (AC4)
        assert resp.headers["content-type"].startswith("text/plain")
        # korelacja: transakcja opłacona i aktywowana
        assert txn.status == PaymentStatus.PAID
        assert txn.paid_amount == Decimal("30.00")
        db.commit.assert_awaited()

    async def test_invalid_md5_answers_400_and_audits(self, client, app):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _scalar(None)])
        _override_auth(app, make_user(), db, role="owner")
        _override_provider(app)

        bad = build_notification(md5sum_override="0" * 32)
        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=bad,
            headers={"Content-Type": "application/x-www-form-urlencoded", "X-JWS-Signature": sign_jws(bad)},
        )

        assert resp.status_code == 400
        assert resp.text == "FALSE"
        event = db.add.call_args.args[0]
        assert event.processing_status == WebhookProcessingStatus.REJECTED_MD5.value
        db.commit.assert_awaited()  # audyt odrzucenia utrwalony mimo 400

    async def test_missing_jws_header_answers_400(self, client, app):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[MagicMock(), _scalar(None)])
        _override_auth(app, make_user(), db, role="owner")
        _override_provider(app)

        resp = await client.post(
            "/api/v1/billing/webhooks/tpay",
            content=build_notification(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert resp.status_code == 400


class TestTransactionStatusEndpoint:
    """AC2/AC7 — status lokalny + jednorazowy fallback reconciliation."""

    async def test_status_pending_without_fallback_below_threshold(self, client, app):
        db = AsyncMock()
        tid = _override_auth(app, make_user(), db, role="owner")
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=tid,
            transaction_id="ta_X",
            hidden_description="ord-1",
            amount=Decimal("30.00"),
            currency="PLN",
            status=PaymentStatus.PENDING,
            created_at=datetime.now(UTC),
            test_mode=False,
            meta={"plan": "basic"},
        )
        db.execute = AsyncMock(side_effect=[_scalar(txn)])
        provider = _override_provider(app)
        provider.get_transaction = AsyncMock()

        resp = await client.get("/api/v1/billing/transactions/ord-1")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert body["plan"] == "basic"
        provider.get_transaction.assert_not_awaited()  # poniżej progu — bez pollingu

    async def test_status_reconciles_after_threshold(self, client, app):
        """AC7: pending > próg → jednorazowe get_transaction u tpay."""
        from app.services.billing.providers.base import ProviderTransaction

        db = AsyncMock()
        tid = _override_auth(app, make_user(), db, role="owner")
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=tid,
            transaction_id="ta_X",
            hidden_description="ord-1",
            amount=Decimal("30.00"),
            currency="PLN",
            status=PaymentStatus.PENDING,
            created_at=datetime.now(UTC) - timedelta(minutes=5),  # dawno temu
            meta={"plan": "premium"},
        )
        db.execute = AsyncMock(
            side_effect=[
                _scalar(txn),  # select txn
                _scalar(SubscriptionPlan(id=uuid.uuid4(), name=PlanName.PREMIUM, display_name="Premium")),
                _scalar(None),  # subskrypcja: nowa
                MagicMock(),  # UPDATE tenants.plan
            ]
        )
        provider = _override_provider(app)
        provider.get_transaction = AsyncMock(
            return_value=ProviderTransaction(
                transaction_id="ta_X",
                status="paid",
                amount=Decimal("30.00"),
                paid_amount=Decimal("30.00"),
                test_mode=True,
            )
        )

        resp = await client.get("/api/v1/billing/transactions/ord-1")

        assert resp.status_code == 200
        provider.get_transaction.assert_awaited_once_with("ta_X")
        assert txn.status == PaymentStatus.PAID  # reconciliation → paid + aktywacja
        assert resp.json()["status"] == "paid"
        db.commit.assert_awaited()

    async def test_other_tenants_transaction_404(self, client, app):
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),  # obcy tenant
            hidden_description="ord-x",
            amount=Decimal("30.00"),
            currency="PLN",
            status=PaymentStatus.PENDING,
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(txn)])
        _override_auth(app, make_user(), db, role="owner")
        _override_provider(app)

        resp = await client.get("/api/v1/billing/transactions/ord-x")
        assert resp.status_code == 404


class TestCheckoutBlikRefuseNoPayId:
    """Story 7.2 AC7 — bank bez Płatności Powtarzalnych BLIK (refuseNoPayId)."""

    async def test_refuse_no_pay_id_maps_to_422_with_card_suggestion(self, client, app):
        """Sandbox: kwota 495.00 + opis mock → błąd refuseNoPayId → komunikat
        z wyjaśnieniem i sugestią zapisu karty (AC2)."""
        from app.services.billing.providers.tpay.client import TpayApiError

        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="owner")
        provider = _override_provider(app)
        provider.create_checkout = AsyncMock(side_effect=TpayApiError(400, "err: refuseNoPayId"))
        # brak aktywnej subskrypcji płatnej (1 select)
        db.execute = AsyncMock(side_effect=[_scalar(None)])

        resp = await client.post("/api/v1/billing/checkout", json={"plan": "basic"})

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "BLIK" in detail or "blik" in detail.lower()
        assert "kart" in detail.lower()  # sugestia zapisu karty

    async def test_other_tpay_errors_still_502(self, client, app):
        from app.services.billing.providers.tpay.client import TpayApiError

        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="owner")
        provider = _override_provider(app)
        provider.create_checkout = AsyncMock(side_effect=TpayApiError(500, "internal"))
        db.execute = AsyncMock(side_effect=[_scalar(None)])

        resp = await client.post("/api/v1/billing/checkout", json={"plan": "basic"})
        assert resp.status_code == 502


class TestWebhookRecurringHandling:
    """Story 7.2 AC5/AC6 — webhook dla odnowień (source=recurring)."""

    def _post(self, client, body):
        return client.post(
            "/api/v1/billing/webhooks/tpay",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "X-JWS-Signature": sign_jws(body)},
        )

    def _txn(self, meta):
        return PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            hidden_description="ord-r",
            amount=Decimal("30.00"),
            currency="PLN",
            status=PaymentStatus.PENDING,
            meta=meta,
        )

    async def test_recurring_paid_renews_instead_of_activating(self, client, app):
        """Task 5.4: paid odnowienia → przedłużenie okresu (nie reset od teraz)."""
        from app.models.subscription import Subscription, SubscriptionStatus

        txn = self._txn({"plan": "premium", "source": "recurring", "payer_email": "o@t.pl"})
        period_end = datetime.now(UTC) + timedelta(days=2)
        sub = Subscription(
            id=uuid.uuid4(),
            tenant_id=txn.tenant_id,
            plan_id=uuid.uuid4(),
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.now(UTC) - timedelta(days=28),
            current_period_end=period_end,
            next_charge_at=period_end,
            cancel_at_period_end=False,
            dunning_attempt=2,
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL RLS
                _scalar(None),  # dedup
                _scalar(txn),  # korelacja
                _scalar(sub),  # renew: get_current_subscription
                MagicMock(),  # UPDATE tenants.plan
            ]
        )
        _override_auth(app, make_user(), db, role="owner")
        _override_provider(app)

        resp = await self._post(client, build_notification(tr_crc="ord-r"))

        assert resp.status_code == 200
        assert txn.status == PaymentStatus.PAID
        # przedłużenie od końca okresu + next_charge_at = nowy koniec (AC5)
        assert sub.current_period_start == period_end
        assert sub.next_charge_at == sub.current_period_end
        assert sub.dunning_attempt == 0  # czyszczenie dunningu

    async def test_recurring_declined_enters_dunning_not_charged_back(self, client, app):
        """AC6: odmowa odnowienia (tr_status=false) → dunning, nie CHARGED_BACK."""
        from app.models.subscription import Subscription, SubscriptionStatus

        txn = self._txn({"plan": "basic", "source": "recurring", "payer_email": "o@t.pl"})
        sub = Subscription(
            id=uuid.uuid4(),
            tenant_id=txn.tenant_id,
            plan_id=uuid.uuid4(),
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.now(UTC) - timedelta(days=30),
            current_period_end=datetime.now(UTC),
            next_charge_at=datetime.now(UTC),
            cancel_at_period_end=False,
            dunning_attempt=0,
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                _scalar(None),  # dedup
                _scalar(txn),  # korelacja
                _scalar(sub),  # declined: get_current_subscription
            ]
        )
        _override_auth(app, make_user(), db, role="owner")
        _override_provider(app)

        resp = await self._post(
            client,
            build_notification(tr_crc="ord-r", tr_status="false", tr_paid="0.00"),
        )

        assert resp.status_code == 200
        assert txn.status == PaymentStatus.PENDING  # nie charged_back
        assert sub.dunning_attempt == 1  # próba 1 → retry D+1
        assert sub.dunning_next_retry_at is not None

    async def test_recurring_chargeback_flagged_for_manual_review(self, client, app):
        """Task 6.4: chargeback na odnowieniu → flaga ręcznej weryfikacji."""
        txn = self._txn({"plan": "basic", "source": "recurring"})
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                _scalar(None),  # dedup
                _scalar(txn),  # korelacja
            ]
        )
        _override_auth(app, make_user(), db, role="owner")
        _override_provider(app)

        resp = await self._post(client, build_notification(tr_crc="ord-r", tr_status="chargeback", tr_paid="30.00"))

        assert resp.status_code == 200
        assert txn.status == PaymentStatus.CHARGED_BACK
        assert txn.meta.get("manual_review") is True  # flaga admina

    async def test_checkout_paid_with_card_token_saves_payment_token(self, client, app):
        """AC1: webhook checkout (save=1) z card_token → zapis PaymentToken."""
        from app.models.payment import PaymentToken, TokenKind, TpayTokenStatus
        from app.models.subscription import Subscription, SubscriptionStatus

        txn = self._txn({"plan": "basic"})
        sub = Subscription(
            id=uuid.uuid4(),
            tenant_id=txn.tenant_id,
            plan_id=uuid.uuid4(),
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            cancel_at_period_end=False,
        )
        db = AsyncMock()
        db.begin_nested = MagicMock(return_value=savepoint_cm())  # savepoint faktury (7.6 hook)
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL
                _scalar(None),  # dedup
                _scalar(txn),  # korelacja
                _scalar(SubscriptionPlan(id=uuid.uuid4(), name=PlanName.BASIC, display_name="Basic")),  # plan
                _scalar(sub),  # subskrypcja (aktywacja)
                MagicMock(),  # UPDATE tenants.plan
                _scalar(None),  # save token: digest → brak
                _scalar(sub),  # save token: link z subskrypcją
            ]
        )
        _override_auth(app, make_user(), db, role="owner")
        _override_provider(app)

        # 7.6: faktura po paid — poza zakresem tego testu (zapis karty),
        # hook mockowany, żeby nie doładowywał dodatkowych db.execute.
        from unittest.mock import patch

        with (
            patch("app.services.billing.webhook_processor.InvoiceService") as inv_svc,
            patch("app.workers.tasks.generate_invoice_pdf.generate_invoice_pdf") as invoice_task,
        ):
            inv_svc.return_value.generate_invoice = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
            resp = await self._post(client, build_notification(tr_crc="ord-r", card_token="tbe_save1"))
            invoice_task.delay.assert_called_once()

        assert resp.status_code == 200
        added = [c.args[0] for c in db.add.call_args_list]
        token = next(t for t in added if isinstance(t, PaymentToken))
        assert token.kind == TokenKind.CARD_TOKEN
        assert token.tpay_status == TpayTokenStatus.ACTIVE
        assert token.card_tail == "0016"
        assert token.card_brand == "mastercard"
        assert sub.payment_token_id == token.id  # AC1: powiązanie z subskrypcją
