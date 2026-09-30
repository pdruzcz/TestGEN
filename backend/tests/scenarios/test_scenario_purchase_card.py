"""Scenariusze 2-3 (AC2/AC3) — zakup kartą (sukces + zapis tokena) i przelew PBL.

E2E z mockami tpay (Task 2.2). Karta: dane testowe sandbox (np. Mastercard
``2223 0002 8000 0016`` / Visa ``4056 2178 4359 7258``, CVC 3 losowe cyfry,
przyszła data — §2.1); przy ``pay.cardPaymentData.save=1`` tpay dołącza
``card_token`` do notyfikacji → ``PaymentToken`` zapisany (7.2 AC1).
PBL: wybór banku na Panelu Transakcyjnym, opłacenie symulowane webhookek
``tr_status=true`` (identyczny kontrakt transakcyjny).
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.payment import PaymentStatus, PaymentToken, TokenKind, TpayTokenStatus
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName
from app.services.billing.providers.base import CheckoutResult
from tests.fixtures.billing_fixtures import (
    added_objects,
    billing_emails_mocked,
    install_app_overrides,
    invoice_pipeline_mocked,
    make_mock_db,
    make_plans,
    make_scenario_provider,
    make_subscription,
    owner_user,
    paid_webhook_db,
    paid_webhook_results,
    post_tpay_notification,
    scalar,
)
from tests.fixtures.tpay_fixtures import (
    TPAY_TEST_CARD_EXPIRY,
    TPAY_TEST_CARDS,
    TPAY_TEST_CVV,
    build_notification,
)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _checkout_db(sub, freemium_plan):
    return make_mock_db(scalar(sub), scalar(freemium_plan))


async def _init_checkout(client, app, *, sub, freemium_plan, provider, user, plan_key="basic"):
    provider.create_checkout = AsyncMock(
        return_value=CheckoutResult(
            transaction_id="ta_card_1",
            transaction_payment_url="https://secure.sandbox.tpay.com/panel/card",
        )
    )
    db = _checkout_db(sub, freemium_plan)
    install_app_overrides(app, user=user, db=db, provider=provider)
    resp = await client.post("/api/v1/billing/checkout", json={"plan": plan_key})
    assert resp.status_code == 200, resp.text
    return added_objects(db)[0]


class TestScenario2CardPurchase:
    """AC2 — zakup kartą testową (sukces) + zapis tokena przy save=1."""

    async def test_card_success_with_save_saves_payment_token(self, client, app):
        plans = make_plans()
        basic = plans[PlanName.BASIC]
        freemium = plans[PlanName.FREEMIUM]
        user = owner_user()
        sub = make_subscription(freemium)
        provider = make_scenario_provider()

        # Karta testowa sandbox + CVC/data ważności (§2.1 — na Panelu tpay).
        assert "2223000280000016" in TPAY_TEST_CARDS
        assert len(TPAY_TEST_CVV) == 3

        txn = await _init_checkout(client, app, sub=sub, freemium_plan=freemium, provider=provider, user=user)

        # save=1 → notyfikacja z card_token/card_tail/card_brand (7.2 AC1).
        db2 = make_mock_db(
            *paid_webhook_results(txn, basic, sub),
            scalar(None),  # save_card_token: dedup po value_digest → brak
            scalar(sub),  # _link_default_method: subskrypcja
        )
        install_app_overrides(app, user=user, db=db2, provider=provider)
        notification = build_notification(
            tr_crc=txn.hidden_description,
            tr_amount="30.00",
            tr_paid="30.00",
            tr_status="true",
            card_token="tbe_card_save1",
        )

        with billing_emails_mocked() as emails, invoice_pipeline_mocked():
            resp = await post_tpay_notification(client, notification)
            assert resp.status_code == 200
            assert resp.text == "TRUE"
            emails["confirmation"].assert_called_once()

        assert txn.status == PaymentStatus.PAID
        assert sub.plan_id == basic.id
        assert sub.status == SubscriptionStatus.ACTIVE

        # PaymentToken zapisany (7.2 AC1): karta domyślną metodą odnowień.
        token = next(t for t in added_objects(db2) if isinstance(t, PaymentToken))
        assert token.kind == TokenKind.CARD_TOKEN
        assert token.tpay_status == TpayTokenStatus.ACTIVE
        assert token.card_tail == "0016"
        assert token.card_brand == "mastercard"
        assert sub.payment_token_id == token.id  # powiązanie z subskrypcją
        assert token.is_default is True


class TestScenario3PblBankTransfer:
    """AC3 — zakup przelewem bankowym (PBL, lista banków sandbox)."""

    async def test_pbl_paid_webhook_activates_plan_and_status_endpoint(self, client, app):
        plans = make_plans()
        premium = plans[PlanName.PREMIUM]
        freemium = plans[PlanName.FREEMIUM]
        user = owner_user()
        sub = make_subscription(freemium)
        provider = make_scenario_provider()

        txn = await _init_checkout(
            client,
            app,
            sub=sub,
            freemium_plan=freemium,
            provider=provider,
            user=user,
            plan_key="premium",
        )

        # Opłacenie przelewem (symulowane) → ten sam kontrakt webhooka.
        db2 = paid_webhook_db(txn, premium, sub)
        install_app_overrides(app, user=user, db=db2, provider=provider)
        with billing_emails_mocked(), invoice_pipeline_mocked():
            resp = await post_tpay_notification(
                client,
                build_notification(tr_crc=txn.hidden_description, tr_amount="50.00", tr_paid="50.00", tr_status="true"),
            )
            assert resp.status_code == 200
            assert resp.text == "TRUE"

        assert txn.status == PaymentStatus.PAID
        assert sub.plan_id == premium.id
        assert sub.status == SubscriptionStatus.ACTIVE

        # Strona powrotu: polling statusu transakcji (7.4 AC2).
        db3 = make_mock_db(scalar(txn))
        install_app_overrides(app, user=user, db=db3, provider=provider)
        status = await client.get(f"/api/v1/billing/transactions/{txn.hidden_description}")
        assert status.status_code == 200
        body = status.json()
        assert body["status"] == "paid"
        assert body["plan"] == "premium"
        assert body["test_mode"] is True
        assert body["amount"] == "50.00"
        # Uwaga (README): notyfikacja transakcyjna tpay nie niesie grupy/kanału
        # płatności — metoda „przelew" nie jest odrębnym polem API (7.6 Dev Record).
        assert txn.title == "TR-123456"
        assert TPAY_TEST_CARD_EXPIRY[0] == "12"  # przyszła data karty (dane sandbox)
