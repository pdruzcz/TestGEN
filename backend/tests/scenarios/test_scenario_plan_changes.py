"""Scenariusze 6-8 (AC6-AC8) — upgrade z proration, downgrade, anulowanie, reaktywacja.

E2E z mockami tpay (Task 3.1), na poziomie serwisów (7.5) + schedulera (7.2):
- upgrade Basic→Premium: kwota prorated liczona lokalnie (D2), zgodność
  preview↔charge, finalizacja po webhooku ``paid`` (``source=plan_change``),
  limity Premium + zachowane liczniki, ``plan_change_history`` z proration;
- Freemium→płatny: pełna cena (bez komponentu prorated);
- downgrade (Premium→Basic, Premium→Freemium, Basic→Freemium): czysto lokalnie
  (§3.5) — ``cancel_at_period_end`` + stop ``next_charge_at``, **bez żadnego
  wywołania API tpay**; egzekucja przez scheduler po ``current_period_end``;
- reaktywacja: ``cancel_pending_change`` przywraca harmonogram obciążeń.

Uwaga: portal bilingowy 7.7 (przyciski FE) oczekuje na implementację —
scenariusze pokrywają semantykę backendową, na której 7.7 będzie operował.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.payment import PaymentStatus, PaymentTransaction
from app.models.plan_change import PlanChangeStatus, PlanChangeType
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName
from app.services.billing.providers.base import CheckoutResult, ProviderTransaction
from app.services.billing.subscription_scheduler import SubscriptionScheduler
from app.services.billing.subscription_service import SubscriptionService
from app.services.billing.webhook_processor import WebhookProcessor
from tests.fixtures.billing_fixtures import (
    added_objects,
    billing_emails_mocked,
    in_days,
    invoice_pipeline_mocked,
    make_change_history,
    make_mock_db,
    make_plans,
    make_scenario_provider,
    make_subscription,
    now_utc,
    saved_card_token,
    scalar,
    scalars,
)
from tests.fixtures.tpay_fixtures import build_notification, sign_jws


class TestScenario6UpgradeProration:
    """AC6 — upgrade z proration (7.5): preview↔charge, finalizacja po `paid`."""

    async def test_upgrade_basic_to_premium_prorated_consistency_and_finalize(self):
        plans = make_plans()
        basic, premium = plans[PlanName.BASIC], plans[PlanName.PREMIUM]
        tenant_id = uuid.uuid4()
        provider = make_scenario_provider()
        provider.charge_recurring = AsyncMock(
            return_value=ProviderTransaction(
                transaction_id="ta_up_1",
                status="pending",
                amount=Decimal("10.00"),
                paid_amount=None,
                test_mode=True,
            )
        )
        # Basic w połowie okresu (15 z 30 dni pełnych), zapisana karta = metoda odnowień.
        period_start = now_utc() - timedelta(days=15)
        sub = make_subscription(basic, tenant_id, period_start=period_start, days=30)
        # Dokładnie 15 pełnych dni do końca (bez obcięcia `.days` na 29/30 okresu).
        sub.current_period_end = now_utc() + timedelta(days=15, minutes=1)
        token = saved_card_token(tenant_id)
        sub.payment_token_id = token.id

        # Podgląd proration (AC5) — lokalnie, bez API tpay.
        db_preview = make_mock_db(scalar(sub), scalar(basic))
        preview = await SubscriptionService(db_preview).preview_proration(tenant_id, PlanName.PREMIUM)
        assert preview["amount"] == "10.00"  # ((50-30)/30 dni) x 15 pozostałych dni
        assert preview["change_type"] == PlanChangeType.UPGRADE.value

        # Obciążenie prorated zapisaną metodą (merchant-initiated, bez redirectu).
        db_change = make_mock_db(
            scalar(sub),  # _get_subscription_locked (FOR UPDATE)
            scalar(basic),  # _plan_of
            scalar(None),  # get_pending_change
            scalar(token),  # _active_subscription_token
        )
        result = await SubscriptionService(db_change).change_plan(
            tenant_id,
            PlanName.PREMIUM,
            None,
            provider=provider,
            owner_email="owner@testcompany.pl",
        )
        assert result.change_type == PlanChangeType.UPGRADE
        assert result.payment_required is True
        # AC6: kwota prorated = lokalne wyliczenie (test zgodności preview↔charge).
        assert result.amount == Decimal(preview["amount"])
        provider.charge_recurring.assert_awaited_once()
        charge_kwargs = provider.charge_recurring.call_args.kwargs
        assert charge_kwargs["amount"] == Decimal("10.00")
        assert charge_kwargs["card_token"] == "tbe_card_1234"  # odszyfrowany token
        assert charge_kwargs["blik_alias"] is None

        history = next(h for h in added_objects(db_change) if h.to_plan == PlanName.PREMIUM)
        assert history.from_plan == PlanName.BASIC
        assert history.status == PlanChangeStatus.PENDING
        assert history.proration_details["amount"] == "10.00"
        txn = next(t for t in added_objects(db_change) if isinstance(t, PaymentTransaction))
        assert txn.meta["source"] == "plan_change"
        assert txn.meta["change_id"] == str(history.id)
        assert txn.amount == Decimal("10.00")

        # Webhook `paid` → finalize_plan_upgrade: plan zmieniony natychmiast.
        db_final = make_mock_db(
            MagicMock(),  # SET LOCAL RLS
            scalar(None),  # dedup
            scalar(txn),  # korelacja tr_crc
            scalar(premium),  # finalize: select planu Premium
            scalar(sub),  # finalize: subskrypcja
            scalar(history),  # finalize: _change_by_id
            MagicMock(),  # UPDATE tenants.plan
        )
        notification = build_notification(
            tr_crc=txn.hidden_description, tr_amount="10.00", tr_paid="10.00", tr_status="true"
        )
        with billing_emails_mocked() as emails, invoice_pipeline_mocked() as (_inv, pdf_task):
            ok, status = await WebhookProcessor(db_final, provider).handle_tpay_notification(
                notification, sign_jws(notification)
            )
            assert ok is True
            pdf_task.delay.assert_called_once()  # faktura po upgrade (7.6)
            emails["confirmation"].assert_called_once()

        assert status == "processed"
        assert txn.status == PaymentStatus.PAID
        assert sub.plan_id == premium.id  # plan zmieniony natychmiast
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.cancel_at_period_end is False
        # Liczniki zachowane + okres bez zmian (pełna stawka od kolejnego cyklu).
        assert sub.current_period_start == period_start
        assert not any(hasattr(o, "counter_type") for o in added_objects(db_final))
        assert history.status == PlanChangeStatus.COMPLETED
        assert history.proration_details["amount"] == "10.00"  # AC6: proration_details w historii
        assert history.effective_at is not None

        # Limity Premium aktywne (analyses unlimited w macierzy 7.1).
        db_limits = make_mock_db(scalar(premium))
        effective = await SubscriptionService(db_limits).get_effective_plan(sub)
        assert effective.features["analyses"] is None

    async def test_upgrade_from_freemium_charges_full_price(self):
        """AC6 (wariant) — Freemium→płatny: pełna cena, bez prorated."""
        plans = make_plans()
        freemium = plans[PlanName.FREEMIUM]
        tenant_id = uuid.uuid4()
        provider = make_scenario_provider()
        provider.create_checkout = AsyncMock(
            return_value=CheckoutResult(transaction_id="ta_up_2", transaction_payment_url="https://tpay/pay")
        )
        provider.charge_recurring = AsyncMock()
        sub = make_subscription(freemium, tenant_id)  # brak zapisanej metody

        db_change = make_mock_db(scalar(sub), scalar(freemium), scalar(None), scalar(None))
        result = await SubscriptionService(db_change).change_plan(
            tenant_id,
            PlanName.PREMIUM,
            None,
            provider=provider,
            owner_email="owner@testcompany.pl",
        )
        assert result.amount == Decimal("50.00")  # pełna cena — bez komponentu prorated
        assert result.payment_required is True
        assert result.payment_url == "https://tpay/pay"  # checkout redirect (brak metody)
        provider.charge_recurring.assert_not_awaited()


class TestScenario7DowngradeAndCancel:
    """AC7 — downgrade (warianty) i anulowanie: lokalnie, bez wywołań tpay."""

    @pytest.mark.parametrize(
        ("from_key", "to_key"),
        [("premium", "basic"), ("premium", "freemium"), ("basic", "freemium")],
    )
    async def test_downgrade_schedules_period_end_without_tpay_calls(self, from_key, to_key):
        plans = make_plans()
        current = plans[PlanName(from_key)]
        tenant_id = uuid.uuid4()
        provider = make_scenario_provider()
        provider.create_checkout = AsyncMock()
        provider.charge_recurring = AsyncMock()
        sub = make_subscription(current, tenant_id)

        db_change = make_mock_db(scalar(sub), scalar(current), scalar(None))
        result = await SubscriptionService(db_change).change_plan(
            tenant_id,
            PlanName(to_key),
            None,
            provider=provider,
            owner_email="owner@testcompany.pl",
        )
        assert result.change_type == PlanChangeType.DOWNGRADE
        assert result.payment_required is False
        assert result.amount == Decimal("0.00")  # bez zwrotów (AC2 7.5)
        # cancel_at_period_end=true + next_charge_at zatrzymane.
        assert sub.cancel_at_period_end is True
        assert sub.next_charge_at is None
        # Asercja AC7: żądanie do API tpay NIE jest wysyłane.
        provider.create_checkout.assert_not_called()
        provider.charge_recurring.assert_not_awaited()

        (history,) = added_objects(db_change)
        assert history.change_type == PlanChangeType.DOWNGRADE
        assert history.status == PlanChangeStatus.PENDING
        assert history.effective_at == sub.current_period_end  # efektywny na koniec okresu

    async def test_scheduled_downgrade_executed_after_period_end(self):
        """AC7 — po przekroczeniu current_period_end scheduler zmienia plan
        i egzekwuje jego limity (mock czasu: run(now=...) z przyszłą datą)."""
        plans = make_plans()
        premium, freemium = plans[PlanName.PREMIUM], plans[PlanName.FREEMIUM]
        tenant_id = uuid.uuid4()
        provider = make_scenario_provider()
        provider.create_checkout = AsyncMock()
        provider.charge_recurring = AsyncMock()
        sub = make_subscription(premium, tenant_id, days=2)  # koniec okresu za 2 dni
        sub.cancel_at_period_end = True  # zaplanowany downgrade (Premium→Freemium)
        sub.next_charge_at = None
        history = make_change_history(
            tenant_id,
            from_plan=PlanName.PREMIUM,
            to_plan=PlanName.FREEMIUM,
            change_type=PlanChangeType.DOWNGRADE,
        )

        db_run = make_mock_db(
            scalars(),  # skan odnowień (next_charge_at=None → pusto)
            scalars(),  # skan wygasłych grace
            scalars(sub),  # skan downgrade'ów do egzekucji
            scalar(premium),  # stary plan (nazwa w emailu)
            scalar(history),  # get_pending_change
            scalar(freemium),  # plan docelowy
            MagicMock(),  # UPDATE tenants.plan → freemium
            scalar("owner@testcompany.pl"),  # email Ownera
        )
        run_at = in_days(3)  # po przekroczeniu current_period_end (mock czasu)
        with billing_emails_mocked() as emails:
            stats = await SubscriptionScheduler(db_run, provider).run(now=run_at)
        assert stats.get("downgraded") == 1

        assert sub.plan_id == freemium.id  # plan docelowy ustawiony
        assert sub.cancel_at_period_end is False
        assert sub.next_charge_at is None  # Freemium — koniec obciążeń
        assert sub.current_period_end == run_at + timedelta(days=30)  # nowy okres Freemium
        assert history.status == PlanChangeStatus.COMPLETED
        emails["plan_changed"].assert_called_once()  # powiadomienie o zmianie

        # Egzekwuje limity planu docelowego (Freemium: analyses 10).
        db_limits = make_mock_db(scalar(freemium))
        effective = await SubscriptionService(db_limits).get_effective_plan(sub)
        assert effective.features["analyses"] == 10


class TestScenario8Reactivation:
    """AC8 — reaktywacja anulowanej subskrypcji (bez wywołania tpay)."""

    async def test_reactivate_restores_charge_schedule(self):
        plans = make_plans()
        premium = plans[PlanName.PREMIUM]
        tenant_id = uuid.uuid4()
        provider = make_scenario_provider()
        provider.create_checkout = AsyncMock()
        provider.charge_recurring = AsyncMock()
        sub = make_subscription(premium, tenant_id, days=10)
        sub.cancel_at_period_end = True  # anulowana (aktywna do końca okresu)
        sub.next_charge_at = None
        history = make_change_history(
            tenant_id,
            from_plan=PlanName.PREMIUM,
            to_plan=PlanName.FREEMIUM,
            change_type=PlanChangeType.DOWNGRADE,
        )

        db_reactivate = make_mock_db(scalar(history), scalar(sub))
        canceled = await SubscriptionService(db_reactivate).cancel_pending_change(tenant_id)

        assert canceled.status == PlanChangeStatus.CANCELED
        assert sub.cancel_at_period_end is False  # subskrypcja kontynuowana
        assert sub.next_charge_at == sub.current_period_end  # przywrócony harmonogram
        assert sub.plan_id == premium.id  # plan płatny bez zmian
        provider.create_checkout.assert_not_called()
        provider.charge_recurring.assert_not_awaited()
