"""Scenariusze 9-10 (AC9/AC10) — odnowienia cykliczne: token karty i alias BLIK PAYID.

E2E z mockami tpay (Task 4.1). tpay nie ma silnika subskrypcji (D2) —
``SubscriptionScheduler`` (7.2) tworzy obciążenie merchant-initialized
(``pay.cardPaymentData.token`` / ``blikPaymentData.type=2``), a webhook
``paid`` przedłuża okres (``renew_subscription``). Alias BLIK rejestruje się
na kwotach z groszami x.08-x.15 (aliasy żyją ≥ tydzień; kody 999xxx są
czyszczone co 15 min — nie polegać). ``ALIAS_EXPIRED`` zawiesza token +
powiadomienie Ownera; ``495.00`` + opis ``mock`` → refuseNoPayId (bank bez
Płatności Powtarzalnych) → komunikat z sugestią karty.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.payment import PaymentStatus, PaymentTransaction, TpayTokenStatus
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName
from app.services.billing.providers.base import ProviderTransaction
from app.services.billing.subscription_scheduler import SubscriptionScheduler
from app.services.billing.webhook_processor import WebhookProcessor
from tests.fixtures.billing_fixtures import (
    added_objects,
    billing_emails_mocked,
    in_days,
    install_app_overrides,
    invoice_pipeline_mocked,
    make_mock_db,
    make_payment_txn,
    make_plans,
    make_scenario_provider,
    make_subscription,
    owner_user,
    saved_blik_alias,
    saved_card_token,
    scalar,
    scalars,
)
from tests.fixtures.tpay_fixtures import (
    TPAY_BANK_NO_REPEATABLE_AMOUNT,
    build_alias_notification,
    build_notification,
    payid_amount,
    sign_jws,
)


def _scheduler_db(sub, *, plan, token, owner_email="owner@testcompany.pl"):
    """Sekwencja ``execute`` przebiegu schedulera z jednym odnowieniem."""
    return make_mock_db(
        scalars(sub),  # skan odnowień (next_charge_at <= now)
        scalars(),  # skan wygasłych grace
        scalars(),  # skan downgrade'ów
        scalar(plan),  # _process_renewal: plan
        scalar(token),  # _process_renewal: metoda płatności
        scalar(owner_email),  # _owner_email
    )


class TestScenario9CardTokenRenewal:
    """AC9 — odnowienie cykliczne kartą (token) + webhook paid."""

    async def test_scheduler_charges_token_and_webhook_renews_period(self):
        plans = make_plans()
        basic = plans[PlanName.BASIC]
        tenant_id = uuid.uuid4()
        provider = make_scenario_provider()
        provider.charge_recurring = AsyncMock(
            return_value=ProviderTransaction(
                transaction_id="ta_ren_1",
                status="pending",
                amount=Decimal("30.00"),
                paid_amount=None,
                test_mode=True,
            )
        )
        token = saved_card_token(tenant_id)
        sub = make_subscription(basic, tenant_id, days=2)  # next_charge_at za 2 dni
        sub.payment_token_id = token.id
        old_period_end = sub.current_period_end

        # Przebieg schedulera po terminie obciążenia (mock czasu).
        db_run = _scheduler_db(sub, plan=basic, token=token)
        stats = await SubscriptionScheduler(db_run, provider).run(now=in_days(3))
        assert stats.get("charged") == 1

        # Obciążenie merchant-initiated: token karty, kwota planu (30 PLN).
        provider.charge_recurring.assert_awaited_once()
        kwargs = provider.charge_recurring.call_args.kwargs
        assert kwargs["card_token"] == "tbe_card_1234"
        assert kwargs["blik_alias"] is None
        assert kwargs["amount"] == Decimal("30.00")
        assert "odnowienie" in kwargs["description"]

        (txn,) = [t for t in added_objects(db_run) if isinstance(t, PaymentTransaction)]
        assert txn.status == PaymentStatus.PENDING
        assert txn.meta["source"] == "recurring"
        assert txn.meta["plan"] == "basic"
        assert txn.amount == Decimal("30.00")

        # Webhook `paid` przedłuża okres: ciągłość rozliczeń od old_period_end.
        db_webhook = make_mock_db(
            MagicMock(),  # SET LOCAL RLS
            scalar(None),  # dedup
            scalar(txn),  # korelacja tr_crc
            scalar(sub),  # renew_subscription: subskrypcja
            MagicMock(),  # UPDATE tenants.plan
        )
        notification = build_notification(
            tr_crc=txn.hidden_description, tr_amount="30.00", tr_paid="30.00", tr_status="true"
        )
        with billing_emails_mocked() as emails, invoice_pipeline_mocked() as (_inv, pdf_task):
            ok, status = await WebhookProcessor(db_webhook, provider).handle_tpay_notification(
                notification, sign_jws(notification)
            )
            assert ok is True
            pdf_task.delay.assert_called_once()  # faktura z odnowienia (7.6)
            emails["confirmation"].assert_called_once()

        assert status == "processed"
        assert txn.status == PaymentStatus.PAID
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.current_period_start == old_period_end  # przedłużenie, nie reset
        assert sub.current_period_end == old_period_end + timedelta(days=30)  # next_charge_at += cykl
        assert sub.next_charge_at == sub.current_period_end
        assert sub.dunning_attempt == 0  # czyszczenie stanu dunningu


class TestScenario10BlikPayidRenewal:
    """AC10 — odnowienie aliasem BLIK PAYID + wygaśnięcie aliasu + refuseNoPayId."""

    async def test_scheduler_charges_blik_alias_payid(self):
        """Alias zarejestrowany na kwocie x.08-x.15 → odnowienie bez udziału
        użytkownika (``blikPaymentData.type=2`` → ``blik_alias`` w charge)."""
        plans = make_plans()
        basic = plans[PlanName.BASIC]
        tenant_id = uuid.uuid4()
        provider = make_scenario_provider()
        provider.charge_recurring = AsyncMock(
            return_value=ProviderTransaction(
                transaction_id="ta_ren_blik",
                status="pending",
                amount=Decimal("30.00"),
                paid_amount=None,
                test_mode=True,
            )
        )
        alias = saved_blik_alias(tenant_id, value="tg-alias-payid-1")
        sub = make_subscription(basic, tenant_id, days=2)
        sub.payment_token_id = alias.id

        # Rejestracja aliasu nastąpiła na checkoutu z kwotą w zakresie PAYID.
        assert payid_amount("30") == "30.08"  # x.08 in x.08-x.15 (§2.1)

        db_run = _scheduler_db(sub, plan=basic, token=alias)
        stats = await SubscriptionScheduler(db_run, provider).run(now=in_days(3))
        assert stats.get("charged") == 1

        kwargs = provider.charge_recurring.call_args.kwargs
        assert kwargs["blik_alias"] == "tg-alias-payid-1"  # obciążenie aliasem
        assert kwargs["card_token"] is None

    async def test_alias_expired_suspends_token_and_notifies_owner(self):
        """Notyfikacja ``ALIAS_EXPIRED`` → ``PaymentToken`` suspended +
        powiadomienie Ownera (dodaj kartę / ponów BLIK)."""
        provider = make_scenario_provider()
        tenant_id = uuid.uuid4()
        alias = saved_blik_alias(tenant_id, value="tg-alias-payid-1")
        plans = make_plans()
        sub = make_subscription(plans[PlanName.BASIC], tenant_id, days=20)  # cykliczna, aktywna
        registration_txn = make_payment_txn(
            tenant_id,
            amount=payid_amount("30"),
            meta={"blik_alias_value": "tg-alias-payid-1", "payer_email": "owner@testcompany.pl"},
        )

        db = make_mock_db(
            MagicMock(),  # SET LOCAL RLS
            scalar(None),  # dedup
            scalar(registration_txn),  # korelacja aliasu po transakcji rejestracji
            scalar(alias),  # find_blik_alias_token (digest)
            scalar(sub),  # _notify_owner_if_recurring: subskrypcja cykliczna
        )
        notification = build_alias_notification(event="ALIAS_EXPIRED", alias_value="tg-alias-payid-1")
        with billing_emails_mocked() as emails:
            ok, status = await WebhookProcessor(db, provider).handle_tpay_notification(
                notification, sign_jws(notification)
            )
        assert ok is True
        assert status == "processed"
        assert alias.tpay_status == TpayTokenStatus.SUSPENDED  # PaymentToken zaktualizowany
        emails["method_expired"].assert_called_once()
        assert emails["method_expired"].call_args.kwargs["email"] == "owner@testcompany.pl"
        assert emails["method_expired"].call_args.kwargs["method"] == "alias BLIK"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestScenario10BankWithoutRepeatablePayments:
    """AC10 (odmowa banku) — kwota 495.00 + opis mock → refuseNoPayId → 422."""

    async def test_refuse_no_pay_id_suggests_card(self, client, app):
        from app.services.billing.providers.tpay.client import TpayApiError

        plans = make_plans()
        user = owner_user()
        sub = make_subscription(plans[PlanName.FREEMIUM])
        provider = make_scenario_provider()
        provider.create_checkout = AsyncMock(side_effect=TpayApiError(400, "err: refuseNoPayId"))
        db = make_mock_db(scalar(sub), scalar(plans[PlanName.FREEMIUM]))
        install_app_overrides(app, user=user, db=db, provider=provider)

        resp = await client.post("/api/v1/billing/checkout", json={"plan": "basic"})
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert TPAY_BANK_NO_REPEATABLE_AMOUNT == "495.00"
        assert "BLIK" in detail
        assert "kart" in detail.lower()  # sugestia: zapłać kartą i zapisz ją
