"""Unit tests for billing models and SubscriptionService — Story 7.1.

Covers AC1 (3-plan data model), AC2 (Freemium on registration),
AC4/AC5 helpers (plans + limits from a single source of truth).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import inspect

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.usage import CounterType, UsageCounter


def _columns(model) -> dict[str, object]:
    return {c.name: c for c in inspect(model).columns}


class TestSubscriptionPlanModel:
    """AC1 — SubscriptionPlan table shape (3 plans, no yearly price, no provider fields)."""

    def test_tablename(self):
        assert SubscriptionPlan.__tablename__ == "subscription_plans"

    def test_columns_present(self):
        cols = _columns(SubscriptionPlan)
        for name in (
            "id",
            "name",
            "display_name",
            "price_monthly",
            "currency",
            "features",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        ):
            assert name in cols, f"missing column {name}"

    def test_no_yearly_and_no_provider_fields(self):
        cols = _columns(SubscriptionPlan)
        # Decyzja 2026-08-28: brak pól rocznych; D1: tpay nie ma price_id
        assert "price_yearly" not in cols
        assert not any("tpay" in c or "stripe" in c or "provider" in c for c in cols)

    def test_plan_name_enum_values(self):
        assert {p.value for p in PlanName} == {"freemium", "basic", "premium"}

    def test_price_monthly_is_numeric(self):
        assert _columns(SubscriptionPlan)["price_monthly"].type.python_type is Decimal


class TestSubscriptionModel:
    """AC1/AC2 — Subscription: one active subscription per tenant, our own (no stripe_*)."""

    def test_tablename(self):
        assert Subscription.__tablename__ == "subscriptions"

    def test_columns_present(self):
        cols = _columns(Subscription)
        for name in (
            "id",
            "tenant_id",
            "plan_id",
            "status",
            "current_period_start",
            "current_period_end",
            "next_charge_at",
            "cancel_at_period_end",
            "trial_end",
            "created_at",
            "updated_at",
        ):
            assert name in cols, f"missing column {name}"

    def test_no_stripe_fields(self):
        cols = _columns(Subscription)
        assert not any("stripe" in c for c in cols)

    def test_status_enum_values(self):
        assert {s.value for s in SubscriptionStatus} == {"active", "past_due", "canceled", "incomplete"}

    def test_cancel_at_period_end_defaults_false(self):
        default = _columns(Subscription)["cancel_at_period_end"].default
        assert default is not None and default.arg is False

    def test_tenant_id_unique(self):
        # unique=True + index=True → unikalny indeks (odpowiednik UNIQUE w PG)
        unique_indexes = [[c.name for c in ix.columns] for ix in Subscription.__table__.indexes if ix.unique]
        assert ["tenant_id"] in unique_indexes


class TestUsageCounterModel:
    """AC1 — UsageCounter: no `users`, no `api_requests` (decyzje 2026-08-28)."""

    def test_tablename(self):
        assert UsageCounter.__tablename__ == "usage_counters"

    def test_counter_type_values(self):
        assert {c.value for c in CounterType} == {"analyses", "test_cases", "storage_bytes", "files_per_analysis"}

    def test_columns_present(self):
        cols = _columns(UsageCounter)
        for name in ("id", "tenant_id", "counter_type", "value", "limit_value", "period_start", "period_end"):
            assert name in cols, f"missing column {name}"

    def test_value_defaults_zero(self):
        default = _columns(UsageCounter)["value"].default
        assert default is not None and default.arg == 0


class TestBillingSchemas:
    """AC4 — Pydantic schemas for the billing API."""

    def test_plan_out_serializes_price_as_str(self):
        from app.schemas.billing import PlanOut

        plan = SubscriptionPlan(
            id=uuid.uuid4(),
            name=PlanName.BASIC,
            display_name="Basic",
            price_monthly=Decimal("30.00"),
            currency="PLN",
            features={"analyses": 50},
            is_active=True,
            sort_order=1,
        )
        out = PlanOut.model_validate(plan, from_attributes=True)
        data = out.model_dump(mode="json")
        assert data["price_monthly"] == "30.00"
        assert data["name"] == "basic"

    def test_subscription_out(self):
        from app.schemas.billing import SubscriptionOut

        sub = Subscription(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC),
            cancel_at_period_end=False,
        )
        out = SubscriptionOut.model_validate(sub, from_attributes=True)
        assert out.status == "active"

    def test_plan_comparison_out_carries_legal_urls(self):
        from app.schemas.billing import PlanComparisonOut

        payload = PlanComparisonOut(
            plans=[],
            current_plan="freemium",
            terms_url="https://test-gen.pl/regulamin/",
            privacy_policy_url="https://test-gen.pl/polityka/",
        )
        assert payload.terms_url.startswith("https://")


class TestModelsExported:
    def test_models_exported_from_package(self):
        from app.models import (  # noqa: F401
            Subscription,
            SubscriptionPlan,
            UsageCounter,
        )


def _mock_db_with_plans(existing: list) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = existing
    db.execute.return_value = result
    db.add = MagicMock()  # sync method on AsyncSession
    return db


def _added_plans(db: AsyncMock) -> list:
    return [call.args[0] for call in db.add.call_args_list]


class TestBillingSettings:
    """AC5 — ceny i URL-e prawne z env (§3.2a)."""

    def test_defaults(self):
        from app.core.config_billing import BillingSettings

        s = BillingSettings()
        assert s.billing_basic_monthly_price == Decimal("30.00")
        assert s.billing_premium_monthly_price == Decimal("50.00")
        assert s.billing_currency == "PLN"
        assert s.billing_terms_url == "https://test-gen.pl/regulamin/"
        assert s.billing_privacy_policy_url == "https://test-gen.pl/polityka/"


class TestSeedSubscriptionPlans:
    """AC1/AC5 — seed 3 planów, ceny z env, idempotentny re-seed."""

    async def test_seed_creates_three_plans_in_order(self):
        from app.seed.seed_plans import seed_subscription_plans

        db = _mock_db_with_plans([])
        await seed_subscription_plans(db)
        added = _added_plans(db)
        assert [p.name.value for p in added] == ["freemium", "basic", "premium"]
        assert [p.sort_order for p in added] == [0, 1, 2]

    async def test_seed_freemium_always_free(self):
        from app.core.config_billing import BillingSettings
        from app.seed.seed_plans import seed_subscription_plans

        settings = BillingSettings(billing_basic_monthly_price=Decimal("30.00"))
        db = _mock_db_with_plans([])
        await seed_subscription_plans(db, settings=settings)
        added = _added_plans(db)
        assert added[0].name.value == "freemium"
        assert added[0].price_monthly == Decimal("0.00")
        assert added[0].currency == settings.billing_currency

    async def test_seed_prices_from_settings(self):
        from app.core.config_billing import BillingSettings
        from app.seed.seed_plans import seed_subscription_plans

        settings = BillingSettings(
            billing_basic_monthly_price=Decimal("12.50"),
            billing_premium_monthly_price=Decimal("99.00"),
        )
        db = _mock_db_with_plans([])
        await seed_subscription_plans(db, settings=settings)
        added = {p.name.value: p for p in _added_plans(db)}
        assert added["basic"].price_monthly == Decimal("12.50")
        assert added["premium"].price_monthly == Decimal("99.00")

    async def test_seed_reseed_updates_prices_no_duplicates(self):
        from app.core.config_billing import BillingSettings
        from app.seed.seed_plans import seed_subscription_plans

        existing = SubscriptionPlan(
            id=uuid.uuid4(),
            name=PlanName.BASIC,
            display_name="Basic",
            price_monthly=Decimal("20.00"),
            currency="PLN",
            features={},
            is_active=True,
            sort_order=1,
        )
        db = _mock_db_with_plans([existing])
        await seed_subscription_plans(db, settings=BillingSettings(billing_basic_monthly_price=Decimal("30.00")))
        added_names = [p.name.value for p in _added_plans(db)]
        assert "basic" not in added_names  # istniejący plan nie jest tworzony od nowa
        assert existing.price_monthly == Decimal("30.00")  # cena zaktualizowana z env

    async def test_seed_features_matrix_approved_values(self):
        from app.seed.seed_plans import seed_subscription_plans

        db = _mock_db_with_plans([])
        await seed_subscription_plans(db)
        by_name = {p.name.value: p for p in _added_plans(db)}

        assert [
            by_name["freemium"].features["analyses"],
            by_name["basic"].features["analyses"],
            by_name["premium"].features["analyses"],
        ] == [10, 50, None]
        assert [by_name[n].features["test_cases"] for n in ("freemium", "basic", "premium")] == [50, 250, None]
        assert [by_name[n].features["storage_bytes"] for n in ("freemium", "basic", "premium")] == [
            500 * 1024 * 1024,
            5 * 1024**3,
            10 * 1024**3,
        ]
        assert [by_name[n].features["files_per_analysis"] for n in ("freemium", "basic", "premium")] == [5, 25, 50]
        assert [by_name[n].features["rate_limit_per_min"] for n in ("freemium", "basic", "premium")] == [100, 100, 1000]
        assert [by_name[n].features["priority_support"] for n in ("freemium", "basic", "premium")] == [
            False,
            False,
            True,
        ]

        # Zakazane wymiary (decyzje 2026-08-28): users unlimited, API calls/dzień usunięty
        for name in ("freemium", "basic", "premium"):
            feats = by_name[name].features
            assert "users" not in feats
            assert "api_calls_per_day" not in feats
            assert feats["llm_cost_tracking"] is False  # 7.10 usunięte

    async def test_seed_gated_modules_complete(self):
        from app.seed.seed_plans import seed_subscription_plans

        db = _mock_db_with_plans([])
        await seed_subscription_plans(db)
        gated = _added_plans(db)[0].features["gated_modules"]
        # kod + TC = freemium; docs/UML/GUI/integration+CI-CD = basic; security/premium stuff = premium
        assert gated["code_analysis"] == "freemium"
        assert gated["test_generation"] == "freemium"
        for m in ("documentation", "uml", "gui", "integration_tests", "ci_cd"):
            assert gated[m] == "basic", m
        for m in ("security", "security_recommendations", "code_doc_consistency", "functional_gaps"):
            assert gated[m] == "premium", m

    async def test_seed_populates_quota_limits_cache(self):
        """Seed z DB zasilają cache limitów QuotaService — jedno źródło prawdy."""
        from app.seed.seed_plans import seed_subscription_plans
        from app.services import quota_service

        quota_service.clear_plan_limits_cache()
        db = _mock_db_with_plans([])
        await seed_subscription_plans(db)

        assert quota_service.get_analysis_limit(PlanName.FREEMIUM) == 10
        assert quota_service.get_analysis_limit(PlanName.BASIC) == 50
        assert quota_service.get_analysis_limit(PlanName.PREMIUM) is None  # unlimited
        quota_service.clear_plan_limits_cache()


class TestPlanTypeThreeTiers:
    """7.1/2b.1 — Tenant.plan na enum 3-planowy, PlanName tym samym enumem."""

    def test_plan_type_values(self):
        from app.models.tenant import PlanType

        assert {p.value for p in PlanType} == {"freemium", "basic", "premium"}

    def test_tenant_default_plan_freemium(self):
        from app.models.tenant import PlanType, Tenant

        default = _columns(Tenant)["plan"].default
        assert default is not None and default.arg == PlanType.FREEMIUM

    def test_plan_name_is_plan_type(self):
        from app.models.tenant import PlanType

        assert PlanName is PlanType  # jedno źródło enumu w całym kodzie


def _freemium_plan() -> SubscriptionPlan:
    return SubscriptionPlan(
        id=uuid.uuid4(),
        name=PlanName.FREEMIUM,
        display_name="Freemium",
        price_monthly=Decimal("0.00"),
        currency="PLN",
        features={"analyses": 10, "test_cases": 50},
        is_active=True,
        sort_order=0,
    )


def _mock_db_execute_sequence(results: list) -> AsyncMock:
    """AsyncMock sesji z sekwencją wyników execute (scalar/scalars wg użycia)."""
    db = AsyncMock()
    db.add = MagicMock()
    results_iter = iter(results)
    db.execute = AsyncMock(side_effect=lambda *a, **k: next(results_iter))
    return db


def _exec_scalars_all(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _exec_scalar_one_or_none(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


class TestSubscriptionService:
    """AC2/AC4 — SubscriptionService: plany, subskrypcja Freemium, limity z DB, check_quota."""

    async def test_get_plans_returns_active_sorted(self):
        from app.services.billing.subscription_service import SubscriptionService

        freemium = SubscriptionPlan(name=PlanName.FREEMIUM, sort_order=0, is_active=True)
        premium = SubscriptionPlan(name=PlanName.PREMIUM, sort_order=2, is_active=True)
        # mock zwraca wiersze tak, jak posortowałaby baza — sortowanie robi SQL
        db = _mock_db_execute_sequence([_exec_scalars_all([freemium, premium])])

        plans = await SubscriptionService(db).get_plans()

        assert [p.name for p in plans] == [PlanName.FREEMIUM, PlanName.PREMIUM]
        stmt = db.execute.call_args.args[0]
        assert "ORDER BY subscription_plans.sort_order" in str(stmt)
        assert "WHERE subscription_plans.is_active" in str(stmt)

    async def test_get_current_subscription_found(self):
        from app.services.billing.subscription_service import SubscriptionService

        sub = Subscription(id=uuid.uuid4(), tenant_id=uuid.uuid4(), plan_id=uuid.uuid4())
        db = _mock_db_execute_sequence([_exec_scalar_one_or_none(sub)])

        found = await SubscriptionService(db).get_current_subscription(sub.tenant_id)
        assert found is sub

    async def test_get_current_subscription_none(self):
        from app.services.billing.subscription_service import SubscriptionService

        db = _mock_db_execute_sequence([_exec_scalar_one_or_none(None)])
        assert await SubscriptionService(db).get_current_subscription(uuid.uuid4()) is None

    async def test_get_plan_limits_reads_features_from_db(self):
        from app.services.billing.subscription_service import SubscriptionService

        plan = _freemium_plan()
        db = _mock_db_execute_sequence([_exec_scalar_one_or_none(plan)])

        limits = await SubscriptionService(db).get_plan_limits(PlanName.FREEMIUM)

        assert limits["analyses"] == 10
        assert limits["test_cases"] == 50

    async def test_create_freemium_subscription(self):
        from app.services.billing.subscription_service import SubscriptionService

        plan = _freemium_plan()
        tenant_id = uuid.uuid4()
        db = _mock_db_execute_sequence(
            [
                _exec_scalar_one_or_none(None),  # brak istniejącej subskrypcji
                _exec_scalar_one_or_none(plan),  # plan freemium
            ]
        )

        sub = await SubscriptionService(db).create_freemium_subscription(tenant_id)

        added = db.add.call_args.args[0]
        assert isinstance(added, Subscription)
        assert added.tenant_id == tenant_id
        assert added.plan_id == plan.id
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.current_period_end > sub.current_period_start  # okno miesięczne

    async def test_create_freemium_subscription_idempotent(self):
        from app.services.billing.subscription_service import SubscriptionService

        existing = Subscription(
            id=uuid.uuid4(), tenant_id=uuid.uuid4(), plan_id=uuid.uuid4(), status=SubscriptionStatus.ACTIVE
        )
        db = _mock_db_execute_sequence([_exec_scalar_one_or_none(existing)])

        sub = await SubscriptionService(db).create_freemium_subscription(existing.tenant_id)

        assert sub is existing
        db.add.assert_not_called()

    async def test_check_quota_under_limit_true(self):
        from app.models.usage import CounterType, UsageCounter
        from app.services.billing.subscription_service import SubscriptionService

        plan = _freemium_plan()  # analyses: 10
        sub = Subscription(tenant_id=uuid.uuid4(), plan_id=plan.id)
        counter = UsageCounter(tenant_id=sub.tenant_id, counter_type=CounterType.ANALYSES, value=3, limit_value=10)
        db = _mock_db_execute_sequence(
            [
                _exec_scalar_one_or_none(sub),  # subskrypcja
                _exec_scalar_one_or_none(plan),  # plan (limity z features)
                _exec_scalar_one_or_none(counter),  # licznik bieżącego okresu
            ]
        )

        assert await SubscriptionService(db).check_quota(sub.tenant_id, CounterType.ANALYSES) is True

    async def test_check_quota_at_limit_false(self):
        from app.models.usage import CounterType, UsageCounter
        from app.services.billing.subscription_service import SubscriptionService

        plan = _freemium_plan()  # analyses: 10
        sub = Subscription(tenant_id=uuid.uuid4(), plan_id=plan.id)
        counter = UsageCounter(tenant_id=sub.tenant_id, counter_type=CounterType.ANALYSES, value=10, limit_value=10)
        db = _mock_db_execute_sequence(
            [
                _exec_scalar_one_or_none(sub),
                _exec_scalar_one_or_none(plan),
                _exec_scalar_one_or_none(counter),
            ]
        )

        assert await SubscriptionService(db).check_quota(sub.tenant_id, CounterType.ANALYSES) is False

    async def test_check_quota_unlimited_plan_true(self):
        from app.models.usage import CounterType
        from app.services.billing.subscription_service import SubscriptionService

        plan = SubscriptionPlan(
            id=uuid.uuid4(), name=PlanName.PREMIUM, features={"analyses": None}, is_active=True, sort_order=2
        )
        sub = Subscription(tenant_id=uuid.uuid4(), plan_id=plan.id)
        db = _mock_db_execute_sequence(
            [
                _exec_scalar_one_or_none(sub),
                _exec_scalar_one_or_none(plan),
            ]
        )

        assert await SubscriptionService(db).check_quota(sub.tenant_id, CounterType.ANALYSES) is True

    async def test_check_quota_no_counter_row_true(self):
        from app.models.usage import CounterType
        from app.services.billing.subscription_service import SubscriptionService

        plan = _freemium_plan()
        sub = Subscription(tenant_id=uuid.uuid4(), plan_id=plan.id)
        db = _mock_db_execute_sequence(
            [
                _exec_scalar_one_or_none(sub),
                _exec_scalar_one_or_none(plan),
                _exec_scalar_one_or_none(None),  # brak licznika → 0 użycia
            ]
        )

        assert await SubscriptionService(db).check_quota(sub.tenant_id, CounterType.ANALYSES) is True


class TestSubscriptionPortalService:
    """Story 7.7 — cancel/reactivate (AC4/AC5, lokalnie bez tpay) + detail (AC3)."""

    def _basic_plan(self) -> SubscriptionPlan:
        return SubscriptionPlan(
            id=uuid.uuid4(),
            name=PlanName.BASIC,
            display_name="Basic",
            price_monthly=Decimal("30.00"),
            currency="PLN",
            is_active=True,
        )

    def _sub(self, plan, *, cancel=False, charge=True, status=SubscriptionStatus.ACTIVE, days=30):
        from datetime import timedelta

        end = datetime.now(UTC) + timedelta(days=days)
        return Subscription(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            plan_id=plan.id,
            status=status,
            current_period_start=datetime.now(UTC),
            current_period_end=end,
            next_charge_at=end if charge else None,
            cancel_at_period_end=cancel,
        )

    def _exec_scalar_one(self, value) -> MagicMock:
        result = MagicMock()
        result.scalar_one.return_value = value
        return result

    async def test_cancel_sets_flag_and_stops_next_charge(self):
        from app.services.billing.subscription_service import SubscriptionService

        plan = self._basic_plan()
        sub = self._sub(plan)
        db = _mock_db_execute_sequence(
            [
                _exec_scalar_one_or_none(sub),  # locked sub
                _exec_scalar_one_or_none(None),  # brak pending change
                _exec_scalar_one_or_none(plan),  # plan (guard Freemium)
            ]
        )

        returned = await SubscriptionService(db).cancel_subscription(sub.tenant_id)

        assert returned is sub
        assert sub.cancel_at_period_end is True
        assert sub.next_charge_at is None
        stmt = str(db.execute.call_args_list[0].args[0])
        assert "FOR UPDATE" in stmt  # serializacja zmian per-tenant (wzorzec 7.5)

    async def test_cancel_freemium_conflict(self):
        import pytest

        from app.core.exceptions import ConflictError
        from app.services.billing.subscription_service import SubscriptionService

        freemium = _freemium_plan()
        sub = self._sub(freemium)
        db = _mock_db_execute_sequence(
            [_exec_scalar_one_or_none(sub), _exec_scalar_one_or_none(None), _exec_scalar_one_or_none(freemium)]
        )

        with pytest.raises(ConflictError):
            await SubscriptionService(db).cancel_subscription(sub.tenant_id)

    async def test_cancel_already_cancelled_conflict(self):
        import pytest

        from app.core.exceptions import ConflictError
        from app.services.billing.subscription_service import SubscriptionService

        plan = self._basic_plan()
        sub = self._sub(plan, cancel=True, charge=False)
        db = _mock_db_execute_sequence(
            [_exec_scalar_one_or_none(sub), _exec_scalar_one_or_none(None), _exec_scalar_one_or_none(plan)]
        )

        with pytest.raises(ConflictError):
            await SubscriptionService(db).cancel_subscription(sub.tenant_id)

    async def test_cancel_with_pending_downgrade_idempotent(self):
        """AC4 — zaplanowany downgrade (7.5) ma pierwszeństwo (plan niższy)."""
        from app.models.plan_change import PlanChangeHistory, PlanChangeStatus, PlanChangeType
        from app.services.billing.subscription_service import SubscriptionService

        plan = self._basic_plan()
        sub = self._sub(plan, cancel=True, charge=False)
        pending = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=sub.tenant_id,
            from_plan=PlanName.PREMIUM,
            to_plan=PlanName.BASIC,
            change_type=PlanChangeType.DOWNGRADE,
            requested_at=datetime.now(UTC),
            status=PlanChangeStatus.PENDING,
        )
        db = _mock_db_execute_sequence(
            [_exec_scalar_one_or_none(sub), _exec_scalar_one_or_none(pending), _exec_scalar_one_or_none(plan)]
        )

        returned = await SubscriptionService(db).cancel_subscription(sub.tenant_id)

        assert returned is sub
        assert pending.status == PlanChangeStatus.PENDING  # rekord nietknięty

    async def test_reactivate_restores_next_charge(self):
        from app.services.billing.subscription_service import SubscriptionService

        plan = self._basic_plan()
        sub = self._sub(plan, cancel=True, charge=False)
        db = _mock_db_execute_sequence([_exec_scalar_one_or_none(sub), _exec_scalar_one_or_none(None)])

        returned = await SubscriptionService(db).reactivate_subscription(sub.tenant_id)

        assert returned is sub
        assert sub.cancel_at_period_end is False
        assert sub.next_charge_at == sub.current_period_end

    async def test_reactivate_not_cancelled_conflict(self):
        import pytest

        from app.core.exceptions import ConflictError
        from app.services.billing.subscription_service import SubscriptionService

        plan = self._basic_plan()
        sub = self._sub(plan)  # cancel=False
        db = _mock_db_execute_sequence([_exec_scalar_one_or_none(sub), _exec_scalar_one_or_none(None)])

        with pytest.raises(ConflictError):
            await SubscriptionService(db).reactivate_subscription(sub.tenant_id)

    async def test_reactivate_period_ended_conflict(self):
        import pytest

        from app.core.exceptions import ConflictError
        from app.services.billing.subscription_service import SubscriptionService

        plan = self._basic_plan()
        sub = self._sub(plan, cancel=True, charge=False, days=-1)
        db = _mock_db_execute_sequence([_exec_scalar_one_or_none(sub), _exec_scalar_one_or_none(None)])

        with pytest.raises(ConflictError):
            await SubscriptionService(db).reactivate_subscription(sub.tenant_id)

    async def test_get_transactions_orders_desc_with_tenant_filter(self):
        from app.models.payment import PaymentStatus, PaymentTransaction
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            hidden_description=str(uuid.uuid4()),
            amount=Decimal("30.00"),
            status=PaymentStatus.PAID,
        )
        db = _mock_db_execute_sequence(
            [self._exec_scalar_one(1), _exec_scalars_all([txn]), _exec_scalars_all([])]  # count, strona, faktury
        )

        items, total = await SubscriptionService(db).get_transactions(tenant_id)

        assert total == 1
        assert items[0].transaction is txn
        assert items[0].method is None
        stmt = str(db.execute.call_args_list[1].args[0])
        assert "ORDER BY payment_transactions.created_at DESC" in stmt

    async def test_get_transactions_method_from_invoice(self):
        from app.models.payment import PaymentStatus, PaymentTransaction
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            hidden_description=str(uuid.uuid4()),
            amount=Decimal("30.00"),
            status=PaymentStatus.PAID,
        )
        invoice = MagicMock()
        invoice.payment_id = txn.id
        invoice.payment_method = type("M", (), {"value": "bank_transfer"})()
        db = _mock_db_execute_sequence(
            [self._exec_scalar_one(1), _exec_scalars_all([txn]), _exec_scalars_all([invoice])]
        )

        items, _total = await SubscriptionService(db).get_transactions(tenant_id)

        assert items[0].method == "bank_transfer"
        assert items[0].invoice is invoice
