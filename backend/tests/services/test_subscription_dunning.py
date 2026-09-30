"""Testy dunningu — Story 7.2 (AC6; Task 8.3).

Harmonogram ponowień D+1/D+3/D+5 (3 próby), po 3. porażce downgrade ZAWSZE
do Freemium + 7-dniowy grace na planie, który był (CR#2), powiadomienia,
odnowienie po paid (czyszczenie dunningu), wygaśnięcie grace.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.services.billing import subscription_service as svc_mod
from app.services.billing.subscription_service import DUNNING_GRACE_DAYS, SubscriptionService


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _plan(name: PlanName, plan_id=None) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=plan_id or uuid.uuid4(),
        name=name,
        display_name=name.capitalize(),
        price_monthly=50 if name == PlanName.PREMIUM else 30,
        currency="PLN",
        features={"analyses": 50},
    )


def _sub(paid_plan: SubscriptionPlan, **kw) -> Subscription:
    now = datetime.now(UTC)
    fields = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        plan_id=paid_plan.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=30),
        current_period_end=now,
        next_charge_at=now,
        cancel_at_period_end=False,
        dunning_attempt=0,
    )
    fields.update(kw)
    return Subscription(**fields)


def _db(*results) -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=list(results))
    return db


class TestRegisterFailedCharge:
    """AC6 — eskalacja prób: D+1, D+3, D+5, po 3. porażce downgrade."""

    async def test_first_failure_schedules_d1(self):
        premium = _plan(PlanName.PREMIUM)
        sub = _sub(premium)
        db = _db()  # downgrade path nie wykonuje selectów przy próbie < 3

        await SubscriptionService(db).register_failed_charge(sub)

        assert sub.dunning_attempt == 1
        assert sub.dunning_next_retry_at is not None
        delta = sub.dunning_next_retry_at - datetime.now(UTC)
        assert timedelta(hours=23) < delta <= timedelta(days=1) + timedelta(hours=1)

    async def test_retry_offsets_d1_d3_d5(self):
        premium = _plan(PlanName.PREMIUM)
        expected = [1, 3, 5]
        for attempt, days in enumerate(expected, start=1):
            sub = _sub(premium, dunning_attempt=attempt - 1)
            db = _db()
            await SubscriptionService(db).register_failed_charge(sub)
            assert sub.dunning_attempt == attempt
            delta = sub.dunning_next_retry_at - datetime.now(UTC)
            assert timedelta(days=days - 1) < delta <= timedelta(days=days, hours=1)

    async def test_fourth_failure_downgrades_to_freemium_with_grace(self):
        """Po 3 nieudanych próbach (ponowieniach): ZAWSZE Freemium + grace 7 dni."""
        premium = _plan(PlanName.PREMIUM)
        freemium = _plan(PlanName.FREEMIUM)
        sub = _sub(premium, dunning_attempt=3)
        db = _db(_scalar(freemium))  # lookup planu freemium

        await SubscriptionService(db).register_failed_charge(sub)

        assert sub.status == SubscriptionStatus.PAST_DUE
        assert sub.plan_id == freemium.id
        assert sub.previous_plan_id == premium.id  # grace na planie, który był
        grace_delta = sub.grace_until - datetime.now(UTC)
        assert timedelta(days=DUNNING_GRACE_DAYS - 1) < grace_delta <= timedelta(days=DUNNING_GRACE_DAYS, hours=1)

    async def test_downgrade_always_to_freemium_from_basic_too(self):
        """CR#2: downgrade NIE „o poziom niżej" — Basic też → Freemium."""
        basic = _plan(PlanName.BASIC)
        freemium = _plan(PlanName.FREEMIUM)
        sub = _sub(basic, dunning_attempt=3)
        db = _db(_scalar(freemium))

        await SubscriptionService(db).register_failed_charge(sub)
        assert sub.plan_id == freemium.id


class TestRenewSubscription:
    """AC5 — po paid (webhook, source=recurring): przedłużenie + czyszczenie dunningu."""

    async def test_renew_extends_period_and_clears_dunning(self):
        premium = _plan(PlanName.PREMIUM)
        period_end = datetime.now(UTC) + timedelta(days=2)
        sub = _sub(
            premium,
            current_period_start=datetime.now(UTC) - timedelta(days=28),
            current_period_end=period_end,
            dunning_attempt=2,
            dunning_next_retry_at=datetime.now(UTC) + timedelta(days=3),
        )
        db = _db(_scalar(sub), MagicMock())  # sub + update tenants.plan

        await SubscriptionService(db).renew_subscription(sub.tenant_id, PlanName.PREMIUM)

        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.current_period_start == period_end  # przedłużenie od końca okresu
        assert sub.current_period_end > period_end
        assert sub.next_charge_at == sub.current_period_end
        assert sub.dunning_attempt == 0
        assert sub.dunning_next_retry_at is None

    async def test_renew_during_grace_restores_previous_plan(self):
        """Spóźnione odnowienie w grace (past_due) → powrót na plan, który był."""
        premium = _plan(PlanName.PREMIUM)
        freemium = _plan(PlanName.FREEMIUM)
        sub = _sub(
            freemium,
            status=SubscriptionStatus.PAST_DUE,
            previous_plan_id=premium.id,
            grace_until=datetime.now(UTC) + timedelta(days=3),
            dunning_attempt=4,
        )
        db = _db(_scalar(sub), MagicMock())  # sub + update tenants.plan

        await SubscriptionService(db).renew_subscription(sub.tenant_id, PlanName.PREMIUM)

        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.plan_id == premium.id
        assert sub.grace_until is None
        assert sub.previous_plan_id is None


class TestGraceExpiry:
    """AC6 — po wygaśnięciu grace: egzekwowanie limitów Freemium."""

    async def test_expired_grace_flips_legacy_tenant_plan(self):
        """Legacy tenants.plan (gating modułów) → freemium po grace."""

        freemium = _plan(PlanName.FREEMIUM)
        premium = _plan(PlanName.PREMIUM)
        sub = _sub(
            freemium,
            status=SubscriptionStatus.PAST_DUE,
            previous_plan_id=premium.id,
            grace_until=datetime.now(UTC) - timedelta(days=1),
        )
        db = _db(MagicMock())  # update tenants.plan → freemium

        await SubscriptionService(db).enforce_grace_expiry(sub)

        assert sub.grace_until is None  # egzekwowane — koniec grace
        # UPDATE tenants.plan → freemium
        update_stmt = db.execute.call_args_list[-1]
        assert update_stmt.args[0].table.name == "tenants"

    async def test_active_grace_not_enforced(self):
        freemium = _plan(PlanName.FREEMIUM)
        sub = _sub(
            freemium,
            status=SubscriptionStatus.PAST_DUE,
            grace_until=datetime.now(UTC) + timedelta(days=5),
        )
        db = _db()

        await SubscriptionService(db).enforce_grace_expiry(sub)
        assert sub.grace_until is not None  # grace nadal aktywny


class TestEffectivePlanForQuota:
    """AC6 — w grace limity planu, który był; po grace — Freemium."""

    async def test_during_grace_uses_previous_paid_plan(self):
        premium = _plan(PlanName.PREMIUM)
        freemium = _plan(PlanName.FREEMIUM)
        sub = _sub(
            freemium,
            status=SubscriptionStatus.PAST_DUE,
            previous_plan_id=premium.id,
            grace_until=datetime.now(UTC) + timedelta(days=3),
        )
        db = _db(_scalar(premium))

        plan = await SubscriptionService(db).get_effective_plan(sub)
        assert plan.name == PlanName.PREMIUM

    async def test_after_grace_uses_current_freemium(self):
        freemium = _plan(PlanName.FREEMIUM)
        sub = _sub(
            freemium,
            status=SubscriptionStatus.PAST_DUE,
            previous_plan_id=uuid.uuid4(),
            grace_until=datetime.now(UTC) - timedelta(days=1),
        )
        db = _db(_scalar(freemium))

        plan = await SubscriptionService(db).get_effective_plan(sub)
        assert plan.name == PlanName.FREEMIUM


class TestDunningNotifications:
    """AC6 — każda porażka + downgrade → powiadomienie Ownera (email PL)."""

    async def test_failure_sends_payment_failed_email(self, monkeypatch):
        sent: list = []
        monkeypatch.setattr(svc_mod, "send_payment_failed_email", lambda **kw: sent.append(kw))

        premium = _plan(PlanName.PREMIUM)
        sub = _sub(premium)
        db = _db()

        await SubscriptionService(db).register_failed_charge(sub, owner_email="owner@t.pl")
        assert len(sent) == 1
        assert sent[0]["email"] == "owner@t.pl"

    async def test_downgrade_sends_downgrade_email(self, monkeypatch):
        sent: list = []
        monkeypatch.setattr(svc_mod, "send_subscription_downgraded_email", lambda **kw: sent.append(kw))

        premium = _plan(PlanName.PREMIUM)
        freemium = _plan(PlanName.FREEMIUM)
        sub = _sub(premium, dunning_attempt=3)
        db = _db(_scalar(freemium))

        await SubscriptionService(db).register_failed_charge(sub, owner_email="owner@t.pl")
        assert len(sent) == 1  # downgrade (płatność nie powiodła się + informacja o downgrade)
