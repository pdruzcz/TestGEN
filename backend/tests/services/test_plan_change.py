"""Testy zmiany planu — Story 7.5 (AC1–AC6; Task 6.1/6.2/6.4/6.5).

Lokalny proration (D2 — liczymy sami, tpay nie ma ``proration_behavior``):
tablica przypadków ``calculate_proration`` (pół okresu, 1 dzień, ostatni
dzień → 0,00, Freemium→płatny = pełna cena), upgrade/downgrade/cancel
pending, egzekucja downgradu w schedulerze, edge cases. DB mockowana
(wzorzec test_payment_tokens); testy niezależne od cen env — ceny podawane
wprost do czystej funkcji, serwis testowany na domyślnych 30/50 PLN.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import inspect

from app.core.exceptions import ConflictError, NotFoundError
from app.models.payment import PaymentStatus, PaymentToken, PaymentTransaction, TokenKind, TpayTokenStatus
from app.models.plan_change import PlanChangeHistory, PlanChangeStatus, PlanChangeType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.services.billing.subscription_service import (
    SubscriptionService,
    calculate_proration,
)

BASIC_PRICE = Decimal("30.00")
PREMIUM_PRICE = Decimal("50.00")


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _plan(name: PlanName, price: Decimal = Decimal("0.00")) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=uuid.uuid4(),
        name=name,
        display_name=name.capitalize(),
        price_monthly=price,
        currency="PLN",
        features={},
    )


def _sub(plan: SubscriptionPlan, tenant_id=None, *, now=None, **kw) -> Subscription:
    now = now or datetime.now(UTC)
    fields = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        # +12h marginesu: serwis liczy własne ``now`` chwilę później — floor
        # dni musi nadal dawać 15 (okres 30 dni, połowa w przód).
        current_period_start=now - timedelta(days=14, hours=12),
        current_period_end=now + timedelta(days=15, hours=12),
        next_charge_at=now + timedelta(days=15, hours=12),
        cancel_at_period_end=False,
        dunning_attempt=0,
    )
    fields.update(kw)
    return Subscription(**fields)


def _db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


class TestPlanChangeHistoryModel:
    """Task 1.1 — kształt tabeli plan_change_history (AC4)."""

    def test_tablename(self):
        assert PlanChangeHistory.__tablename__ == "plan_change_history"

    def test_columns_present(self):
        cols = {c.name for c in inspect(PlanChangeHistory).columns}
        for name in (
            "id",
            "tenant_id",
            "from_plan",
            "to_plan",
            "change_type",
            "effective_at",
            "requested_at",
            "requested_by",
            "status",
            "proration_details",
            "created_at",
            "updated_at",
        ):
            assert name in cols, f"brak kolumny {name}"

    def test_change_type_enum_values(self):
        assert {t.value for t in PlanChangeType} == {"upgrade", "downgrade"}

    def test_status_enum_values(self):
        assert {s.value for s in PlanChangeStatus} == {"pending", "completed", "canceled"}


class TestCalculateProration:
    """AC1/AC5 — czysta funkcja: Decimal, ROUND_HALF_UP, 2 miejsca."""

    def _window(self, *, days_left: int, period_days: int = 30):
        now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
        end = now + timedelta(days=days_left)
        start = end - timedelta(days=period_days)
        return start, end, now

    def test_half_period_basic_to_premium(self):
        # 15 z 30 dni: (50/30)*15 - (30/30)*15 = 25.00 - 15.00 = 10.00
        start, end, now = self._window(days_left=15)
        details = calculate_proration(
            current_plan=PlanName.BASIC,
            new_plan=PlanName.PREMIUM,
            period_start=start,
            period_end=end,
            now=now,
            current_price=BASIC_PRICE,
            new_price=PREMIUM_PRICE,
        )
        assert details["amount"] == "10.00"
        assert details["period_days"] == 30
        assert details["remaining_days"] == 15

    def test_one_day_left(self):
        # 1 z 30 dni: (50-30)/30 * 1 = 0.666... → 0.67 (ROUND_HALF_UP)
        start, end, now = self._window(days_left=1)
        details = calculate_proration(
            current_plan=PlanName.BASIC,
            new_plan=PlanName.PREMIUM,
            period_start=start,
            period_end=end,
            now=now,
            current_price=BASIC_PRICE,
            new_price=PREMIUM_PRICE,
        )
        assert details["amount"] == "0.67"
        assert details["remaining_days"] == 1

    def test_last_day_is_zero(self):
        # Ostatni dzień okresu (mniej niż pełna doba do końca) → 0,00 (AC1).
        now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
        end = now + timedelta(hours=6)
        start = end - timedelta(days=30)
        details = calculate_proration(
            current_plan=PlanName.BASIC,
            new_plan=PlanName.PREMIUM,
            period_start=start,
            period_end=end,
            now=now,
            current_price=BASIC_PRICE,
            new_price=PREMIUM_PRICE,
        )
        assert details["amount"] == "0.00"
        assert details["remaining_days"] == 0

    def test_freemium_to_paid_full_price(self):
        # Freemium=0 → brak komponentu prorated: pełna cena nowego planu (AC1).
        start, end, now = self._window(days_left=7)
        details = calculate_proration(
            current_plan=PlanName.FREEMIUM,
            new_plan=PlanName.PREMIUM,
            period_start=start,
            period_end=end,
            now=now,
            current_price=Decimal("0.00"),
            new_price=PREMIUM_PRICE,
        )
        assert details["amount"] == "50.00"

    def test_rounding_half_up(self):
        # (33.33-30)/30*11 = 1.221 → 1.22; wariant .005 → w górę.
        start, end, now = self._window(days_left=11)
        details = calculate_proration(
            current_plan=PlanName.BASIC,
            new_plan=PlanName.PREMIUM,
            period_start=start,
            period_end=end,
            now=now,
            current_price=Decimal("30.00"),
            new_price=Decimal("41.25"),
        )
        # (41.25-30)/30*11 = 4.125 → ROUND_HALF_UP → 4.13
        assert details["amount"] == "4.13"

    def test_details_for_audit(self):
        # AC4 — proration_details zawiera dane audytowe wyliczenia.
        start, end, now = self._window(days_left=15)
        details = calculate_proration(
            current_plan=PlanName.BASIC,
            new_plan=PlanName.PREMIUM,
            period_start=start,
            period_end=end,
            now=now,
            current_price=BASIC_PRICE,
            new_price=PREMIUM_PRICE,
        )
        assert details["current_price"] == "30.00"
        assert details["new_price"] == "50.00"
        assert details["current_plan"] == "basic"
        assert details["new_plan"] == "premium"


class _ServiceFixture:
    """Wspólny setup: subskrypcja + plany + kolejka wyników DB."""

    def setup_method(self):
        self.db = _db()
        self.svc = SubscriptionService(self.db)
        self.tenant_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.freemium = _plan(PlanName.FREEMIUM)
        self.basic = _plan(PlanName.BASIC, BASIC_PRICE)
        self.premium = _plan(PlanName.PREMIUM, PREMIUM_PRICE)
        self.plans = {p.id: p for p in (self.freemium, self.basic, self.premium)}
        self.plans_by_name = {p.name: p for p in (self.freemium, self.basic, self.premium)}

    def _provider(self) -> AsyncMock:
        provider = AsyncMock()
        checkout = MagicMock()
        checkout.transaction_id = "ta_123"
        checkout.transaction_payment_url = "https://secure.tpay.com/pay/123"
        provider.create_checkout.return_value = checkout
        charge = MagicMock()
        charge.transaction_id = "ta_456"
        provider.charge_recurring.return_value = charge
        return provider


class TestChangePlanValidation(_ServiceFixture):
    """Task 3.2 — walidacje zmiany planu."""

    @pytest.mark.asyncio
    async def test_same_plan_rejected(self):
        sub = _sub(self.basic, self.tenant_id)
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.basic)]
        with pytest.raises(ValueError):
            await self.svc.change_plan(
                self.tenant_id, PlanName.BASIC, self.user_id, provider=self._provider(), owner_email="o@x.pl"
            )

    @pytest.mark.asyncio
    async def test_no_subscription_rejected(self):
        self.db.execute.side_effect = [_scalar(None)]
        with pytest.raises(NotFoundError):
            await self.svc.change_plan(
                self.tenant_id, PlanName.BASIC, self.user_id, provider=self._provider(), owner_email="o@x.pl"
            )

    @pytest.mark.asyncio
    async def test_downgrade_during_dunning_grace_conflict(self):
        # AC/Task 3.2: downgrade podczas grace dunningu → 409.
        sub = _sub(self.premium, self.tenant_id, status=SubscriptionStatus.PAST_DUE)
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.premium)]
        with pytest.raises(ConflictError):
            await self.svc.change_plan(
                self.tenant_id, PlanName.BASIC, self.user_id, provider=self._provider(), owner_email="o@x.pl"
            )


class TestUpgrade(_ServiceFixture):
    """AC1 — upgrade natychmiastowy, prorated."""

    @pytest.mark.asyncio
    async def test_upgrade_with_saved_method_charges_prorated(self):
        now = datetime.now(UTC)
        token = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            kind=TokenKind.CARD_TOKEN,
            value_encrypted=b"",
            tpay_status=TpayTokenStatus.ACTIVE,
        )
        sub = _sub(self.basic, self.tenant_id, now=now, payment_token_id=token.id)
        provider = self._provider()
        # kolejka: subskrypcja, plan bieżący, pending change (brak), token
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.basic), _scalar(None), _scalar(token)]

        with patch(
            "app.services.billing.subscription_service.decrypt_token_value",
            return_value="tok_val",
        ):
            result = await self.svc.change_plan(
                self.tenant_id, PlanName.PREMIUM, self.user_id, provider=provider, owner_email="o@x.pl"
            )

        assert result.payment_required is True
        assert result.payment_url is None  # zapisana metoda — bez redirectu
        provider.charge_recurring.assert_awaited_once()
        kwargs = provider.charge_recurring.await_args.kwargs
        # 15 z 30 dni × (50-30) = 10.00 — kwota z lokalnego proration
        assert kwargs["amount"] == Decimal("10.00")
        assert kwargs["card_token"] == "tok_val"
        # rekord history pending + transakcja pending
        added = [a.args[0] for a in self.db.add.call_args_list]
        history = next(x for x in added if isinstance(x, PlanChangeHistory))
        txn = next(x for x in added if isinstance(x, PaymentTransaction))
        assert history.status == PlanChangeStatus.PENDING
        assert history.change_type == PlanChangeType.UPGRADE
        assert txn.meta["source"] == "plan_change"
        assert txn.meta["plan"] == PlanName.PREMIUM.value
        # plan NIE zmieniony przed webhookiem paid
        assert sub.plan_id == self.basic.id

    @pytest.mark.asyncio
    async def test_upgrade_without_method_returns_checkout_url(self):
        sub = _sub(self.basic, self.tenant_id, payment_token_id=None)
        provider = self._provider()
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.basic), _scalar(None)]

        result = await self.svc.change_plan(
            self.tenant_id, PlanName.PREMIUM, self.user_id, provider=provider, owner_email="o@x.pl"
        )

        assert result.payment_required is True
        assert result.payment_url == "https://secure.tpay.com/pay/123"
        provider.create_checkout.assert_awaited_once()
        assert provider.create_checkout.await_args.kwargs["amount"] == Decimal("10.00")

    @pytest.mark.asyncio
    async def test_upgrade_zero_amount_applies_immediately(self):
        # AC1: prorated ≤ 0,00 → bez obciążenia, zmiana od razu.
        now = datetime.now(UTC)
        sub = _sub(
            self.basic,
            self.tenant_id,
            now=now,
            current_period_start=now - timedelta(days=30, hours=-6),
            current_period_end=now + timedelta(hours=6),
        )
        provider = self._provider()
        # kolejka: sub, plan bieżący, pending (brak), plan docelowy (apply), tenants.plan update
        self.db.execute.side_effect = [
            _scalar(sub),
            _scalar(self.basic),
            _scalar(None),
            _scalar(self.premium),
            MagicMock(),
        ]

        result = await self.svc.change_plan(
            self.tenant_id, PlanName.PREMIUM, self.user_id, provider=provider, owner_email="o@x.pl"
        )

        assert result.payment_required is False
        assert sub.plan_id == self.premium.id
        provider.charge_recurring.assert_not_awaited()
        provider.create_checkout.assert_not_awaited()
        history = next(a.args[0] for a in self.db.add.call_args_list if isinstance(a.args[0], PlanChangeHistory))
        assert history.status == PlanChangeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_upgrade_from_freemium_full_price(self):
        sub = _sub(self.freemium, self.tenant_id, next_charge_at=None, payment_token_id=None)
        provider = self._provider()
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.freemium), _scalar(None)]

        result = await self.svc.change_plan(
            self.tenant_id, PlanName.PREMIUM, self.user_id, provider=provider, owner_email="o@x.pl"
        )

        assert result.payment_required is True
        assert provider.create_checkout.await_args.kwargs["amount"] == Decimal("50.00")

    @pytest.mark.asyncio
    async def test_upgrade_overrides_pending_downgrade(self):
        # Edge 6.5: upgrade podczas pending downgrade — nadpisuje zmianę.
        now = datetime.now(UTC)
        sub = _sub(self.basic, self.tenant_id, now=now, cancel_at_period_end=True, next_charge_at=None)
        pending = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            from_plan=PlanName.BASIC,
            to_plan=PlanName.FREEMIUM,
            change_type=PlanChangeType.DOWNGRADE,
            requested_at=now,
            status=PlanChangeStatus.PENDING,
        )
        provider = self._provider()
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.basic), _scalar(pending)]

        await self.svc.change_plan(
            self.tenant_id, PlanName.PREMIUM, self.user_id, provider=provider, owner_email="o@x.pl"
        )

        assert pending.status == PlanChangeStatus.CANCELED
        assert sub.cancel_at_period_end is False
        assert sub.next_charge_at == sub.current_period_end


class TestDowngrade(_ServiceFixture):
    """AC2/AC3 — downgrade na koniec okresu, bez wołania tpay."""

    @pytest.mark.asyncio
    async def test_downgrade_sets_flag_and_stops_charge(self):
        sub = _sub(self.premium, self.tenant_id)
        provider = self._provider()
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.premium), _scalar(None)]

        result = await self.svc.change_plan(
            self.tenant_id, PlanName.BASIC, self.user_id, provider=provider, owner_email="o@x.pl"
        )

        assert sub.cancel_at_period_end is True
        assert sub.next_charge_at is None
        assert result.payment_required is False
        # AC2: NIE wołamy API tpay
        provider.charge_recurring.assert_not_awaited()
        provider.create_checkout.assert_not_awaited()
        history = next(a.args[0] for a in self.db.add.call_args_list if isinstance(a.args[0], PlanChangeHistory))
        assert history.change_type == PlanChangeType.DOWNGRADE
        assert history.status == PlanChangeStatus.PENDING
        assert history.effective_at == sub.current_period_end

    @pytest.mark.asyncio
    async def test_downgrade_two_levels_premium_to_freemium(self):
        # Edge 6.5: downgrade o dwa poziomy.
        sub = _sub(self.premium, self.tenant_id)
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.premium), _scalar(None)]

        await self.svc.change_plan(
            self.tenant_id, PlanName.FREEMIUM, self.user_id, provider=self._provider(), owner_email="o@x.pl"
        )

        history = next(a.args[0] for a in self.db.add.call_args_list if isinstance(a.args[0], PlanChangeHistory))
        assert history.to_plan == PlanName.FREEMIUM

    @pytest.mark.asyncio
    async def test_cancel_pending_change_restores_schedule(self):
        # AC3 — rezygnacja z downgrade przed końcem okresu.
        now = datetime.now(UTC)
        sub = _sub(self.premium, self.tenant_id, now=now, cancel_at_period_end=True, next_charge_at=None)
        pending = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            from_plan=PlanName.PREMIUM,
            to_plan=PlanName.BASIC,
            change_type=PlanChangeType.DOWNGRADE,
            requested_at=now,
            status=PlanChangeStatus.PENDING,
        )
        self.db.execute.side_effect = [_scalar(pending), _scalar(sub)]

        record = await self.svc.cancel_pending_change(self.tenant_id)

        assert record.status == PlanChangeStatus.CANCELED
        assert sub.cancel_at_period_end is False
        assert sub.next_charge_at == sub.current_period_end

    @pytest.mark.asyncio
    async def test_cancel_pending_change_without_pending_404(self):
        self.db.execute.side_effect = [_scalar(None)]
        with pytest.raises(NotFoundError):
            await self.svc.cancel_pending_change(self.tenant_id)


class TestFinalizeUpgrade(_ServiceFixture):
    """AC1 — finalizacja upgrade po webhooku `paid` (korelacja hidden_description)."""

    def _txn(self, from_plan: PlanName, change_id: uuid.UUID) -> PaymentTransaction:
        return PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            provider="tpay",
            hidden_description=str(uuid.uuid4()),
            amount=Decimal("10.00"),
            currency="PLN",
            status=PaymentStatus.PAID,
            meta={
                "plan": PlanName.PREMIUM.value,
                "source": "plan_change",
                "from_plan": from_plan.value,
                "change_id": str(change_id),
                "payer_email": "o@x.pl",
            },
        )

    @pytest.mark.asyncio
    async def test_finalize_paid_to_paid_keeps_period_end(self):
        now = datetime.now(UTC)
        sub = _sub(self.basic, self.tenant_id, now=now)
        period_end = sub.current_period_end
        change = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            from_plan=PlanName.BASIC,
            to_plan=PlanName.PREMIUM,
            change_type=PlanChangeType.UPGRADE,
            requested_at=now,
            status=PlanChangeStatus.PENDING,
        )
        txn = self._txn(PlanName.BASIC, change.id)
        # kolejka: plan docelowy, subskrypcja, history, tenants.plan update
        self.db.execute.side_effect = [_scalar(self.premium), _scalar(sub), _scalar(change), MagicMock()]

        await self.svc.finalize_plan_upgrade(txn)

        assert sub.plan_id == self.premium.id
        assert sub.current_period_end == period_end  # AC1: bez zmian
        assert sub.next_charge_at == period_end  # pełna stawka od kolejnego cyklu
        assert change.status == PlanChangeStatus.COMPLETED
        assert change.effective_at is not None

    @pytest.mark.asyncio
    async def test_finalize_from_freemium_new_period(self):
        now = datetime.now(UTC)
        sub = _sub(self.freemium, self.tenant_id, now=now, next_charge_at=None)
        change = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            from_plan=PlanName.FREEMIUM,
            to_plan=PlanName.PREMIUM,
            change_type=PlanChangeType.UPGRADE,
            requested_at=now,
            status=PlanChangeStatus.PENDING,
        )
        txn = self._txn(PlanName.FREEMIUM, change.id)
        self.db.execute.side_effect = [_scalar(self.premium), _scalar(sub), _scalar(change), MagicMock()]

        await self.svc.finalize_plan_upgrade(txn)

        # AC1: przy Freemium→płatny nowy okres od dnia zakupu
        assert sub.plan_id == self.premium.id
        assert sub.current_period_start >= now - timedelta(minutes=1)
        assert sub.current_period_end > now + timedelta(days=29)
        assert sub.next_charge_at == sub.current_period_end

    @pytest.mark.asyncio
    async def test_finalize_in_grace_period_clears_dunning(self):
        # Edge 6.5 — upgrade opłacony w grace period: status wraca do ACTIVE,
        # stan windykacji (dunning/grace/previous_plan_id) wyczyszczony.
        now = datetime.now(UTC)
        sub = _sub(
            self.basic,
            self.tenant_id,
            now=now,
            status=SubscriptionStatus.PAST_DUE,
            dunning_attempt=3,
            dunning_next_retry_at=now + timedelta(days=1),
            grace_until=now + timedelta(days=5),
            previous_plan_id=self.premium.id,
        )
        change = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            from_plan=PlanName.BASIC,
            to_plan=PlanName.PREMIUM,
            change_type=PlanChangeType.UPGRADE,
            requested_at=now,
            status=PlanChangeStatus.PENDING,
        )
        txn = self._txn(PlanName.BASIC, change.id)
        self.db.execute.side_effect = [_scalar(self.premium), _scalar(sub), _scalar(change), MagicMock()]

        await self.svc.finalize_plan_upgrade(txn)

        assert sub.plan_id == self.premium.id
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.dunning_attempt == 0
        assert sub.dunning_next_retry_at is None
        assert sub.grace_until is None
        assert sub.previous_plan_id is None
        assert change.status == PlanChangeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failed_payment_cancels_change(self):
        # Edge 6.5: nieudana płatność upgrade → rekord canceled, plan bez zmian.
        now = datetime.now(UTC)
        change = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            from_plan=PlanName.BASIC,
            to_plan=PlanName.PREMIUM,
            change_type=PlanChangeType.UPGRADE,
            requested_at=now,
            status=PlanChangeStatus.PENDING,
        )
        txn = self._txn(PlanName.BASIC, change.id)
        self.db.execute.side_effect = [_scalar(change)]

        await self.svc.cancel_failed_plan_change(txn)

        assert change.status == PlanChangeStatus.CANCELED


class TestPreviewConsistency(_ServiceFixture):
    """Task 6.2 — kwota z podglądu (AC5) == kwota obciążenia (AC1)."""

    @pytest.mark.asyncio
    async def test_preview_equals_charge(self):
        now = datetime.now(UTC)
        sub = _sub(self.basic, self.tenant_id, now=now)

        # Podgląd (AC5)
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.basic)]
        preview = await self.svc.preview_proration(self.tenant_id, PlanName.PREMIUM)

        # Obciążenie (AC1) — te same wejścia
        provider = self._provider()
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.basic), _scalar(None)]
        result = await self.svc.change_plan(
            self.tenant_id, PlanName.PREMIUM, self.user_id, provider=provider, owner_email="o@x.pl"
        )

        assert Decimal(preview["amount"]) == result.amount
        assert provider.create_checkout.await_args.kwargs["amount"] == Decimal(preview["amount"])

    @pytest.mark.asyncio
    async def test_preview_same_plan_rejected(self):
        sub = _sub(self.basic, self.tenant_id)
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.basic)]
        with pytest.raises(ValueError):
            await self.svc.preview_proration(self.tenant_id, PlanName.BASIC)

    @pytest.mark.asyncio
    async def test_preview_downgrade_no_proration(self):
        # AC2: przejścia w dół bez komponentu prorated — kwota 0.
        sub = _sub(self.premium, self.tenant_id)
        self.db.execute.side_effect = [_scalar(sub), _scalar(self.premium)]
        preview = await self.svc.preview_proration(self.tenant_id, PlanName.BASIC)
        assert preview["amount"] == "0.00"
        assert preview["change_type"] == "downgrade"


class TestScheduledDowngradeExecution(_ServiceFixture):
    """AC6 — egzekucja zaplanowanego downgradu (SubscriptionScheduler)."""

    @pytest.mark.asyncio
    async def test_execute_downgrade_to_freemium(self):
        now = datetime.now(UTC)
        sub = _sub(
            self.premium,
            self.tenant_id,
            now=now,
            cancel_at_period_end=True,
            next_charge_at=None,
            current_period_end=now - timedelta(hours=1),
        )
        pending = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            from_plan=PlanName.PREMIUM,
            to_plan=PlanName.FREEMIUM,
            change_type=PlanChangeType.DOWNGRADE,
            requested_at=now - timedelta(days=10),
            status=PlanChangeStatus.PENDING,
        )
        # kolejka: pending change, plan docelowy, tenants.plan update
        self.db.execute.side_effect = [_scalar(pending), _scalar(self.freemium), MagicMock()]

        target = await self.svc.execute_scheduled_downgrade(sub, now=now)

        assert target is not None and target.name == PlanName.FREEMIUM
        assert sub.plan_id == self.freemium.id
        assert sub.cancel_at_period_end is False
        assert sub.next_charge_at is None
        assert pending.status == PlanChangeStatus.COMPLETED
        assert pending.effective_at is not None

    @pytest.mark.asyncio
    async def test_execute_downgrade_to_basic_schedules_charge(self):
        # Premium→Basic: obciążenie Basic w najbliższym przebiegu odnowień.
        now = datetime.now(UTC)
        end = now - timedelta(hours=1)
        sub = _sub(
            self.premium,
            self.tenant_id,
            now=now,
            cancel_at_period_end=True,
            next_charge_at=None,
            current_period_end=end,
        )
        pending = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            from_plan=PlanName.PREMIUM,
            to_plan=PlanName.BASIC,
            change_type=PlanChangeType.DOWNGRADE,
            requested_at=now - timedelta(days=10),
            status=PlanChangeStatus.PENDING,
        )
        self.db.execute.side_effect = [_scalar(pending), _scalar(self.basic), MagicMock()]

        target = await self.svc.execute_scheduled_downgrade(sub, now=now)

        assert target is not None and target.name == PlanName.BASIC
        assert sub.plan_id == self.basic.id
        # odnowienie Basic natychmiast wymagalne (ciągłość rozliczeń)
        assert sub.next_charge_at == end

    @pytest.mark.asyncio
    async def test_execute_downgrade_without_pending_defaults_freemium(self):
        # Bez rekordu pending (np. anulowanie z 7.7) → Freemium.
        now = datetime.now(UTC)
        sub = _sub(
            self.premium,
            self.tenant_id,
            now=now,
            cancel_at_period_end=True,
            next_charge_at=None,
            current_period_end=now - timedelta(hours=1),
        )
        self.db.execute.side_effect = [_scalar(None), _scalar(self.freemium), MagicMock()]

        target = await self.svc.execute_scheduled_downgrade(sub, now=now)

        assert target is not None and target.name == PlanName.FREEMIUM
        assert sub.plan_id == self.freemium.id
