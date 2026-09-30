"""Scenariusze 4-5 (AC4/AC5) — 3DS sterowany groszami oraz błędy płatności.

E2E z mockami tpay (Task 2.3). Grosze kwoty sterują scenariuszem 3DS
(§2.1): ``*.x1`` → frictionless, ``*.x3`` → sukces 3DS, ``*.x5`` → błąd 3DS,
``*.x6`` → decline, inne → ekran challenge (aktywacja po potwierdzeniu).
Kwoty błędów: karta/wallety ``500/501/503`` (+``504`` dla tokena), BLIK:
``144`` (odrzucony przez płatnika), ``168`` (przez wystawcę), ``120`` (brak
środków), ``312`` (timeout), ``96`` (limit), ``216`` (bezpieczeństwo).

Porażka nie aktywuje subskrypcji — tenant zostaje na planie wyjściowym
(Freemium/Basic) z możliwością ponowienia (strona powrotu FE + nowy checkout).
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.payment import PaymentStatus
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName
from app.services.billing.providers.base import CheckoutResult
from tests.fixtures.billing_fixtures import (
    billing_emails_mocked,
    declined_webhook_db,
    install_app_overrides,
    invoice_pipeline_mocked,
    make_mock_db,
    make_payment_txn,
    make_plans,
    make_scenario_provider,
    make_subscription,
    owner_user,
    paid_webhook_db,
    post_tpay_notification,
    scalar,
)
from tests.fixtures.tpay_fixtures import (
    TPAY_3DS_CHALLENGE_AMOUNTS,
    TPAY_3DS_SUFFIXES,
    TPAY_BLIK_ERROR_AMOUNTS,
    TPAY_CARD_ERROR_AMOUNTS,
    build_notification,
)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class _Purchase:
    """Wspólny stan scenariusza: tenant Freemium/Basic + checkout (opcjonalny)."""

    def __init__(self, *, sub, plans, user=None):
        self.sub = sub
        self.plans = plans
        self.user = user or owner_user()
        self.provider = make_scenario_provider()
        self.provider.create_checkout = AsyncMock(
            return_value=CheckoutResult(
                transaction_id="ta_3ds_1",
                transaction_payment_url="https://secure.sandbox.tpay.com/panel/3ds",
            )
        )

    async def checkout(self, client, app, *, plan_key="basic"):
        db = make_mock_db(scalar(self.sub), scalar(self.plans[PlanName.FREEMIUM]))
        install_app_overrides(app, user=self.user, db=db, provider=self.provider)
        resp = await client.post("/api/v1/billing/checkout", json={"plan": plan_key})
        assert resp.status_code == 200
        return resp.json()

    async def deliver(self, client, app, txn, *, tr_status, tr_paid):
        """Webhook wyniku obciążenia (po akcji płatnika na Panelu tpay)."""
        if tr_status == "true":
            plan = self.plans[PlanName(txn.meta["plan"])]
            db = paid_webhook_db(txn, plan, self.sub)
        else:
            db = declined_webhook_db(txn)
        install_app_overrides(app, user=self.user, db=db, provider=self.provider)
        with billing_emails_mocked(), invoice_pipeline_mocked():
            return await post_tpay_notification(
                client,
                build_notification(
                    tr_crc=txn.hidden_description,
                    tr_amount=str(txn.amount),
                    tr_paid=tr_paid,
                    tr_status=tr_status,
                ),
            )


def _txn_on_amount(amount: str, *, plan: PlanName = PlanName.BASIC, tenant_id=None):
    """Checkout na kwocie sterującej (grosze/błędy) — transakcja lokalna."""
    import uuid

    return make_payment_txn(
        tenant_id or uuid.uuid4(),
        amount=amount,
        meta={"plan": plan.value, "payer_email": "owner@testcompany.pl"},
    )


class TestScenario4ThreeDsControlCents:
    """AC4 — grosze sterujące scenariuszem 3DS."""

    @pytest.mark.parametrize(
        ("suffix_key", "amount", "expected_active"),
        [
            ("frictionless", "30.01", True),  # *.x1 → 3DS frictionless
            ("success", "30.03", True),  # *.x3 → sukces 3DS
            ("error_3ds", "30.05", False),  # *.x5 → błąd 3DS
            ("decline", "30.06", False),  # *.x6 → decline
        ],
        ids=["x1-frictionless", "x3-success", "x5-error3ds", "x6-decline"],
    )
    async def test_control_cents_decide_activation(self, client, app, suffix_key, amount, expected_active):
        # Notacja tpay „x1" = dowolna złotówka + grosze .01 (§2.1).
        assert TPAY_3DS_SUFFIXES[suffix_key][-1] == amount[-1]
        plans = make_plans()
        freemium_sub = make_subscription(plans[PlanName.FREEMIUM])
        scenario = _Purchase(sub=freemium_sub, plans=plans)
        await scenario.checkout(client, app)  # checkout na kwocie planu

        # Kwota sterująca: obciążenie na grosze x1/x3/x5/x6 (sandbox §2.1).
        txn = _txn_on_amount(amount, tenant_id=scenario.user._tenant_id)
        resp = await scenario.deliver(
            client,
            app,
            txn,
            tr_status="true" if expected_active else "false",
            tr_paid=amount if expected_active else "0.00",
        )
        assert resp.status_code == 200
        assert resp.text == "TRUE"

        if expected_active:
            # *.x1/*.x3 kończą się aktywacją subskrypcji.
            assert txn.status == PaymentStatus.PAID
            assert freemium_sub.plan_id == plans[PlanName.BASIC].id
            assert freemium_sub.status == SubscriptionStatus.ACTIVE
        else:
            # *.x5/*.x6 nie aktywują — tenant zostaje na planie wyjściowym.
            assert txn.status != PaymentStatus.PAID
            assert txn.status == PaymentStatus.CHARGED_BACK  # porażka zakupu → flaga ręcznej weryfikacji
            assert freemium_sub.plan_id == plans[PlanName.FREEMIUM].id
            assert freemium_sub.status == SubscriptionStatus.ACTIVE

    @pytest.mark.parametrize("amount", TPAY_3DS_CHALLENGE_AMOUNTS, ids=lambda a: f"challenge-{a}")
    async def test_challenge_after_confirmation_activates(self, client, app, amount):
        """Dowolne inne grosze → ekran challenge; po potwierdzeniu aktywacja."""
        plans = make_plans()
        sub = make_subscription(plans[PlanName.FREEMIUM])
        scenario = _Purchase(sub=sub, plans=plans)
        await scenario.checkout(client, app)

        txn = _txn_on_amount(amount, tenant_id=scenario.user._tenant_id)
        resp = await scenario.deliver(client, app, txn, tr_status="true", tr_paid=amount)
        assert resp.status_code == 200
        assert resp.text == "TRUE"
        assert txn.status == PaymentStatus.PAID
        assert sub.plan_id == plans[PlanName.BASIC].id


class TestScenario5PaymentErrors:
    """AC5 — kwoty wymuszające błędy (karta/wallety + BLIK)."""

    @pytest.mark.parametrize("amount", TPAY_CARD_ERROR_AMOUNTS, ids=lambda a: f"card-{a}")
    async def test_card_error_amounts_leave_tenant_on_plan(self, client, app, amount):
        plans = make_plans()
        sub = make_subscription(plans[PlanName.FREEMIUM])
        scenario = _Purchase(sub=sub, plans=plans)
        await scenario.checkout(client, app)

        txn = _txn_on_amount(amount)
        resp = await scenario.deliver(client, app, txn, tr_status="false", tr_paid="0.00")
        assert resp.status_code == 200
        assert resp.text == "TRUE"
        assert txn.status != PaymentStatus.PAID
        assert sub.plan_id == plans[PlanName.FREEMIUM].id  # plan wyjściowy

    @pytest.mark.parametrize(
        ("error_name", "amount"),
        sorted(TPAY_BLIK_ERROR_AMOUNTS.items()),
        ids=sorted(TPAY_BLIK_ERROR_AMOUNTS),
    )
    async def test_blik_error_amounts_leave_tenant_on_plan(self, client, app, error_name, amount):
        plans = make_plans()
        sub = make_subscription(plans[PlanName.FREEMIUM])
        scenario = _Purchase(sub=sub, plans=plans)
        await scenario.checkout(client, app)

        txn = _txn_on_amount(amount)
        resp = await scenario.deliver(client, app, txn, tr_status="false", tr_paid="0.00")
        assert resp.status_code == 200
        assert txn.status != PaymentStatus.PAID
        assert sub.plan_id == plans[PlanName.FREEMIUM].id

    async def test_error_visible_on_return_page_and_retry_possible(self, client, app):
        """Błąd widoczny na stronie powrotu (polling statusu) + ponowienie checkoutu."""
        plans = make_plans()
        sub = make_subscription(plans[PlanName.FREEMIUM])
        scenario = _Purchase(sub=sub, plans=plans)
        await scenario.checkout(client, app)

        txn = _txn_on_amount(
            TPAY_BLIK_ERROR_AMOUNTS["rejected_by_payer"],  # 144.00
            tenant_id=scenario.user._tenant_id,
        )
        resp = await scenario.deliver(client, app, txn, tr_status="false", tr_paid="0.00")
        assert resp.status_code == 200

        # Strona powrotu: status „nie opłacona" (FE: komunikat błędu + przycisk ponowienia).
        db_status = make_mock_db(scalar(txn))
        install_app_overrides(app, user=scenario.user, db=db_status, provider=scenario.provider)
        status = await client.get(f"/api/v1/billing/transactions/{txn.hidden_description}")
        assert status.status_code == 200
        assert status.json()["status"] != "paid"

        # Ponowienie: tenant bez aktywnego planu płatnego → nowy checkout OK.
        db_retry = make_mock_db(scalar(sub), scalar(plans[PlanName.FREEMIUM]))
        install_app_overrides(app, user=scenario.user, db=db_retry, provider=scenario.provider)
        retry = await client.post("/api/v1/billing/checkout", json={"plan": "basic"})
        assert retry.status_code == 200
        assert retry.json()["amount"] == "30.00"
