"""Scenariusz 1 (AC1) — zakup planu płatnego BLIK 777xxx (podstawowa ścieżka PL).

E2E z mockami tpay (Task 2.1): checkout (Owner, tenant Freemium, sandbox)
→ opłacenie kodem BLIK ``777xxx`` na Panelu Transakcyjnym (symulowane
webhookiem ``tr_status=true``) → aktywacja planu → faktura VAT (7.6) →
email potwierdzenia (mock — w sandboxie maile do płatników zablokowane,
§4.4 planu) → nowy okres rozliczeniowy.

Kwoty sterujące ≠ ceny planów: asercje kwotowe na cenach z konfiguracji
(env §3.2a — domyślne testowe 30/50 PLN).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.payment import PaymentStatus
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
    post_tpay_notification,
    scalar,
)
from tests.fixtures.tpay_fixtures import blik_code, build_notification


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _checkout_db(sub, freemium_plan):
    """Sekwencja ``execute`` checkoutu: subskrypcja (Freemium) → plan."""
    return make_mock_db(scalar(sub), scalar(freemium_plan))


@pytest.mark.parametrize(
    ("plan_key", "amount"),
    [("basic", "30.00"), ("premium", "50.00")],
    ids=["basic", "premium"],
)
class TestScenario1PurchaseBlik:
    """AC1 — pełny flow zakupu BLIK dla obu planów płatnych."""

    async def test_blik_777_full_flow_activates_plan_with_invoice_and_email(self, client, app, plan_key, amount):
        plans = make_plans()
        plan = plans[PlanName(plan_key)]
        freemium = plans[PlanName.FREEMIUM]
        user = owner_user()
        sub = make_subscription(freemium)
        provider = make_scenario_provider()

        # --- Faza 1: Owner inicjuje checkout (tenant na Freemium) ---
        provider.create_checkout = AsyncMock(
            return_value=CheckoutResult(
                transaction_id="ta_blik_1",
                transaction_payment_url="https://secure.sandbox.tpay.com/panel/blik",
            )
        )
        db = _checkout_db(sub, freemium)
        install_app_overrides(app, user=user, db=db, provider=provider)

        resp = await client.post("/api/v1/billing/checkout", json={"plan": plan_key})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["transaction_payment_url"].startswith("https://secure.sandbox.tpay.com")
        assert body["amount"] == amount  # cena z env (§3.2a), nie kwota sterująca

        (txn,) = added_objects(db)
        assert txn.status == PaymentStatus.PENDING
        assert txn.hidden_description == body["order_id"]  # korelacja tr_crc
        assert txn.amount == Decimal(amount)
        assert txn.meta["blik_alias_value"].startswith("tg-")  # wartość aliasu od merchanta (7.3)
        assert txn.meta["payer_email"] == user.email

        # --- Faza 2: opłacenie kodem BLIK 777xxx → webhook tr_status=true ---
        assert blik_code().startswith("777")  # kod sandbox §2.1
        db2 = paid_webhook_db(txn, plan, sub)
        install_app_overrides(app, user=user, db=db2, provider=provider)
        notification = build_notification(
            tr_crc=txn.hidden_description, tr_amount=amount, tr_paid=amount, tr_status="true"
        )

        with billing_emails_mocked() as emails, invoice_pipeline_mocked() as (_inv, pdf_task):
            resp2 = await post_tpay_notification(client, notification)
            assert resp2.status_code == 200
            assert resp2.text == "TRUE"  # asercja obowiązkowa: odpowiedź = TRUE
            pdf_task.delay.assert_called_once()  # faktura VAT (7.6) po `paid`
            emails["confirmation"].assert_called_once()  # email potwierdzenia (mock)
            assert emails["confirmation"].call_args.kwargs["email"] == user.email

        # Subskrypcja Basic/Premium aktywna po korelacji tr_crc.
        assert txn.status == PaymentStatus.PAID
        assert txn.paid_amount == Decimal(amount)
        assert txn.test_mode is True  # asercja: webhook ma test_mode = 1
        assert txn.title == "TR-123456"
        assert sub.plan_id == plan.id
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.cancel_at_period_end is False
        # Liczniki zresetowane na nowy okres: okres startuje „teraz" — okno
        # miesięczne liczników zaczyna się od nowa (brak wiersza = 0 użycia).
        assert sub.current_period_start > datetime.now(UTC) - timedelta(minutes=1)
        assert sub.next_charge_at == sub.current_period_end  # jedyny cykl: miesięczny
