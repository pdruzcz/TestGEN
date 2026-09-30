"""Testy SubscriptionScheduler — Story 7.2 (AC5; Task 8.2).

Skan odnowień (co dobę): next_charge_at <= dziś AND active AND not cancel,
lock FOR UPDATE SKIP LOCKED (brak podwójnych obciążeń), obciążenie tokenem
karty / aliasem BLIK, porażka → dunning, wygaśnięcie grace. DB mockowana;
query WHERE/FOR UPDATE asertowane na skompilowanym SQL (postgresql dialect).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.models.payment import PaymentToken, TokenKind, TpayTokenStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.services.billing.providers.base import CheckoutResult
from app.services.billing.subscription_service import encrypt_token_value


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _plan(name: PlanName = PlanName.BASIC) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=uuid.uuid4(),
        name=name,
        display_name=name.capitalize(),
        price_monthly=30,
        currency="PLN",
        features={},
    )


def _sub(plan: SubscriptionPlan, tenant_id=None, **kw) -> Subscription:
    now = datetime.now(UTC)
    fields = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=30),
        current_period_end=now - timedelta(days=1),
        next_charge_at=now - timedelta(days=1),
        cancel_at_period_end=False,
    )
    fields.update(kw)
    return Subscription(**fields)


def _card_token(tenant_id) -> PaymentToken:
    return PaymentToken(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind=TokenKind.CARD_TOKEN,
        value_encrypted=encrypt_token_value(tenant_id, "tbe_recur"),
        tpay_status=TpayTokenStatus.ACTIVE,
    )


def _blik_token(tenant_id) -> PaymentToken:
    return PaymentToken(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind=TokenKind.BLIK_ALIAS_PAYID,
        value_encrypted=encrypt_token_value(tenant_id, "777payid"),
        tpay_status=TpayTokenStatus.ACTIVE,
    )


def _due_sql(db) -> str:
    """SQL pierwszego zapytania (skan odnowień) — do asercji filtrów/locka."""
    stmt = db.execute.call_args_list[0].args[0]
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _grace_sql(db) -> str:
    stmt = db.execute.call_args_list[1].args[0]
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


class TestRenewalScan:
    """AC5 — skan next_charge_at, lock, brak podwójnego obciążenia."""

    def test_scan_filters_and_locks(self):
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalars([]), _scalars([]), _scalars([])])

        import asyncio

        asyncio.run(SubscriptionScheduler(db, AsyncMock()).run())

        sql = _due_sql(db)
        assert "next_charge_at" in sql
        assert "dunning_next_retry_at" in sql  # cooldown blokuje podwójny przebieg
        assert "cancel_at_period_end" in sql
        assert "FOR UPDATE SKIP LOCKED" in sql  # AC5: brak podwójnych obciążeń

    def test_grace_expiry_scan_filters(self):
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalars([]), _scalars([]), _scalars([])])

        import asyncio

        asyncio.run(SubscriptionScheduler(db, AsyncMock()).run())

        sql = _grace_sql(db)
        assert "grace_until" in sql
        assert "past_due" in sql


class TestChargeRecurring:
    """AC5 — obciążenie tokenem karty / aliasem BLIK (type=2)."""

    def _run(self, sub, token, provider=None):
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        plan = _plan()
        if provider is None:
            provider = AsyncMock()
            provider.charge_recurring = AsyncMock(
                return_value=CheckoutResult(transaction_id="ta_R", transaction_payment_url="https://x")
            )
        db = AsyncMock()
        # [0] skan due, [1] skan grace, [2] skan downgrade (7.5), [3] plan,
        # [4] token, [5] owner email
        db.execute = AsyncMock(
            side_effect=[
                _scalars([sub]),
                _scalars([]),
                _scalars([]),
                _scalar(plan),
                _scalar(token),
                _scalar("owner@tenant.pl"),
            ]
        )
        import asyncio

        asyncio.run(SubscriptionScheduler(db, provider).run())
        return db, provider

    def test_card_token_charge_creates_pending_txn(self):
        tenant_id = uuid.uuid4()
        sub = _sub(_plan(), tenant_id=tenant_id, payment_token_id=uuid.uuid4())
        token = _card_token(tenant_id)

        db, provider = self._run(sub, token)

        kwargs = provider.charge_recurring.call_args.kwargs
        assert kwargs.get("card_token") == "tbe_recur"
        assert kwargs.get("blik_alias") is None
        assert kwargs.get("amount") == 30  # cena planu z DB
        # PaymentTransaction pending z hidden_description=order_id (webhook 7.4)
        added = [c.args[0] for c in db.add.call_args_list]
        txn = next(t for t in added if type(t).__name__ == "PaymentTransaction")
        assert txn.meta["source"] == "recurring"
        assert txn.meta["plan"] == "basic"
        assert txn.tenant_id == tenant_id
        assert txn.transaction_id == "ta_R"
        # Cooldown ciszy (silence-guard): webhook paid wyczyści
        assert sub.dunning_next_retry_at is not None

    def test_blik_alias_charge_uses_alias(self):
        """BLIK: transakcja z samym aliasem (blikPaymentData.type = 2 — AC5)."""
        tenant_id = uuid.uuid4()
        sub = _sub(_plan(), tenant_id=tenant_id, payment_token_id=uuid.uuid4())
        token = _blik_token(tenant_id)

        _db, provider = self._run(sub, token)

        kwargs = provider.charge_recurring.call_args.kwargs
        assert kwargs.get("blik_alias") == "777payid"
        assert kwargs.get("card_token") is None

    def test_provider_failure_enters_dunning(self):
        """Porażka u tpay → register_failed_charge (próba 1, retry D+1)."""
        from app.services.billing.providers.tpay.client import TpayApiError

        tenant_id = uuid.uuid4()
        sub = _sub(_plan(), tenant_id=tenant_id, payment_token_id=uuid.uuid4())
        token = _card_token(tenant_id)
        provider = AsyncMock()
        provider.charge_recurring = AsyncMock(side_effect=TpayApiError(400, "err"))

        db, _ = self._run(sub, token, provider=provider)

        assert sub.dunning_attempt == 1
        assert sub.dunning_next_retry_at is not None
        # pending usunięty (transakcja nigdy nie powstała u tpay)
        assert db.delete.call_count >= 1

    def test_no_active_token_enters_dunning(self):
        """Brak metody (PENDING/None) → porażka dunningu, bez wołania tpay."""
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        plan = _plan()
        sub = _sub(plan, payment_token_id=None)
        provider = AsyncMock()
        db = AsyncMock()
        # [0] due, [1] grace, [2] downgrade (7.5), [3] plan — brak tokena
        db.execute = AsyncMock(side_effect=[_scalars([sub]), _scalars([]), _scalars([]), _scalar(plan), _scalar(None)])

        import asyncio

        asyncio.run(SubscriptionScheduler(db, provider).run())

        provider.charge_recurring.assert_not_called()
        assert sub.dunning_attempt == 1

    def test_suspended_token_enters_dunning(self):
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        plan = _plan()
        tenant_id = uuid.uuid4()
        sub = _sub(plan, tenant_id=tenant_id, payment_token_id=uuid.uuid4())
        token = _card_token(tenant_id)
        token.tpay_status = TpayTokenStatus.SUSPENDED
        provider = AsyncMock()
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[_scalars([sub]), _scalars([]), _scalars([]), _scalar(plan), _scalar(token), _scalar(None)]
        )

        import asyncio

        asyncio.run(SubscriptionScheduler(db, provider).run())
        provider.charge_recurring.assert_not_called()
        assert sub.dunning_attempt == 1


class TestGraceExpiryPass:
    """AC6 — wygaśnięty grace → enforce (tenants.plan → freemium)."""

    def test_expired_grace_enforced_in_run(self):
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        plan = _plan(PlanName.FREEMIUM)
        sub = _sub(
            plan,
            status=SubscriptionStatus.PAST_DUE,
            next_charge_at=None,
            grace_until=datetime.now(UTC) - timedelta(days=1),
        )
        provider = AsyncMock()
        db = AsyncMock()
        # [0] due (pusto), [1] grace scan → [sub], [2] downgrade (7.5), [3] update tenants
        db.execute = AsyncMock(side_effect=[_scalars([]), _scalars([sub]), _scalars([]), MagicMock()])

        import asyncio

        asyncio.run(SubscriptionScheduler(db, provider).run())

        assert sub.grace_until is None
        tenants_update = db.execute.call_args_list[-1].args[0]
        assert tenants_update.table.name == "tenants"


class TestScheduledDowngradePass:
    """7.5 AC6 — skan i egzekucja zaplanowanych downgrade'ów + email."""

    def test_downgrade_scan_filters_and_locks(self):
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalars([]), _scalars([]), _scalars([])])

        import asyncio

        asyncio.run(SubscriptionScheduler(db, AsyncMock()).run())

        stmt = db.execute.call_args_list[2].args[0]
        sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "cancel_at_period_end" in sql
        assert "current_period_end" in sql
        assert "FOR UPDATE SKIP LOCKED" in sql

    def _run_downgrade(self, sub, old_plan, pending, target_plan, monkeypatch, *, email="owner@tenant.pl"):
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        sent: list[tuple] = []
        monkeypatch.setattr(
            "app.services.email.email_service.send_plan_changed_email",
            lambda *a, **kw: sent.append((a, kw)),
        )
        db = AsyncMock()
        # [0] due, [1] grace, [2] downgrade scan → [sub], [3] stary plan,
        # [4] pending change, [5] plan docelowy, [6] UPDATE tenants, [7] owner email
        db.execute = AsyncMock(
            side_effect=[
                _scalars([]),
                _scalars([]),
                _scalars([sub]),
                _scalar(old_plan),
                _scalar(pending),
                _scalar(target_plan),
                MagicMock(),
                _scalar(email),
            ]
        )
        import asyncio

        stats = asyncio.run(SubscriptionScheduler(db, AsyncMock()).run())
        return db, stats, sent

    def test_executes_pending_downgrade_and_sends_email(self, monkeypatch):
        """Downgrade Premium→Basic po końcu okresu: plan zmieniony + email."""
        from app.models.plan_change import PlanChangeHistory, PlanChangeStatus, PlanChangeType

        premium = _plan(PlanName.PREMIUM)
        basic = _plan(PlanName.BASIC)
        sub = _sub(premium, cancel_at_period_end=True, next_charge_at=None)
        pending = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=sub.tenant_id,
            from_plan=PlanName.PREMIUM,
            to_plan=PlanName.BASIC,
            change_type=PlanChangeType.DOWNGRADE,
            requested_at=datetime.now(UTC) - timedelta(days=10),
            status=PlanChangeStatus.PENDING,
            proration_details={},
        )

        _db, stats, sent = self._run_downgrade(sub, premium, pending, basic, monkeypatch)

        assert stats.get("downgraded") == 1
        assert sub.plan_id == basic.id
        assert sub.cancel_at_period_end is False
        assert pending.status == PlanChangeStatus.COMPLETED
        assert len(sent) == 1
        args, _ = sent[0]
        assert args == ("owner@tenant.pl", "Premium", "Basic")

    def test_email_failure_does_not_break_run(self, monkeypatch):
        from app.models.plan_change import PlanChangeHistory, PlanChangeStatus, PlanChangeType
        from app.services.billing.subscription_scheduler import SubscriptionScheduler

        premium = _plan(PlanName.PREMIUM)
        freemium = _plan(PlanName.FREEMIUM)
        sub = _sub(premium, cancel_at_period_end=True, next_charge_at=None)
        pending = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=sub.tenant_id,
            from_plan=PlanName.PREMIUM,
            to_plan=PlanName.FREEMIUM,
            change_type=PlanChangeType.DOWNGRADE,
            requested_at=datetime.now(UTC) - timedelta(days=10),
            status=PlanChangeStatus.PENDING,
            proration_details={},
        )

        def boom(*a, **kw):
            raise RuntimeError("smtp down")

        monkeypatch.setattr("app.services.email.email_service.send_plan_changed_email", boom)
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _scalars([]),
                _scalars([]),
                _scalars([sub]),
                _scalar(premium),
                _scalar(pending),
                _scalar(freemium),
                MagicMock(),
                _scalar("owner@tenant.pl"),
            ]
        )
        import asyncio

        stats = asyncio.run(SubscriptionScheduler(db, AsyncMock()).run())

        assert stats.get("downgraded") == 1  # email best-effort — przebieg OK
        assert sub.plan_id == freemium.id
        assert sub.next_charge_at is None
