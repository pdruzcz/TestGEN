"""FeatureGatingService tests — Story 7.13 (AC: hierarchia, 402, konfiguracja).

Wzorzec „widoczne-zablokowane": próg modułu z ``subscription_plans.features
.gated_modules`` (seed 7.1 — jedno źródło prawdy), plan tenanta z legacy
``tenants.plan`` (trzymane w sync z subskrypcją). DB mockowana (wzorzec
test_billing_plans).
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import FeatureRequiresPlanError
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.tenant import PlanType
from app.seed.seed_plans import GATED_MODULES
from app.services.billing.feature_gating import FeatureGatingService, require_feature


def _plan_row(name: PlanName, features: dict | None = None) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=uuid.uuid4(),
        name=name,
        display_name=name.value.capitalize(),
        features=features if features is not None else {"gated_modules": dict(GATED_MODULES)},
    )


def _db(*results) -> AsyncMock:
    from unittest.mock import MagicMock

    db = AsyncMock()
    mocks = []
    for item in results:
        r = MagicMock()
        r.scalar_one_or_none.return_value = item
        mocks.append(r)
    db.execute = AsyncMock(side_effect=mocks)
    return db


def _tenant_db(plan: PlanType, plan_row: SubscriptionPlan | None) -> AsyncMock:
    """execute → [Tenant.plan, SubscriptionPlan] — kolejność zapytań serwisu."""
    return _db(plan, plan_row)


def _svc(plan: PlanType) -> FeatureGatingService:
    """Świeży serwis z mockami DB pod wskazany plan tenanta."""
    return FeatureGatingService(_tenant_db(plan, _plan_row(PlanName(plan.value))))


class TestHasFeatureHierarchy:
    """Moduł basic: Freemium locked, Basic/Premium OK; premium: tylko Premium."""

    @pytest.mark.parametrize("plan", [PlanType.BASIC, PlanType.PREMIUM])
    async def test_basic_module_allowed_at_or_above_basic(self, plan):
        assert await _svc(plan).has_feature(uuid.uuid4(), "uml") is True
        assert await _svc(plan).has_feature(uuid.uuid4(), "documentation") is True
        assert await _svc(plan).has_feature(uuid.uuid4(), "gui") is True

    async def test_basic_module_locked_for_freemium(self):
        assert await _svc(PlanType.FREEMIUM).has_feature(uuid.uuid4(), "uml") is False
        assert await _svc(PlanType.FREEMIUM).has_feature(uuid.uuid4(), "documentation") is False

    async def test_premium_module_only_for_premium(self):
        assert await _svc(PlanType.PREMIUM).has_feature(uuid.uuid4(), "security") is True
        assert await _svc(PlanType.BASIC).has_feature(uuid.uuid4(), "security") is False
        assert await _svc(PlanType.FREEMIUM).has_feature(uuid.uuid4(), "code_doc_consistency") is False

    async def test_freemium_modules_never_locked(self):
        """Kod + generowanie TC — zawsze aktywne (próg freemium)."""
        assert await _svc(PlanType.FREEMIUM).has_feature(uuid.uuid4(), "code_analysis") is True
        assert await _svc(PlanType.FREEMIUM).has_feature(uuid.uuid4(), "test_generation") is True


class TestEvaluate:
    async def test_unknown_module_not_gated(self):
        svc = FeatureGatingService(_tenant_db(PlanType.FREEMIUM, _plan_row(PlanName.FREEMIUM)))
        allowed, required = await svc.evaluate(uuid.uuid4(), "does_not_exist")
        assert allowed is True
        assert required is None

    async def test_missing_tenant_row_defaults_to_freemium(self):
        svc = FeatureGatingService(_db(None, _plan_row(PlanName.FREEMIUM)))
        allowed, required = await svc.evaluate(uuid.uuid4(), "security")
        assert allowed is False
        assert required == PlanName.PREMIUM

    async def test_required_plan_reported(self):
        svc = FeatureGatingService(_tenant_db(PlanType.BASIC, _plan_row(PlanName.BASIC)))
        allowed, required = await svc.evaluate(uuid.uuid4(), "security")
        assert allowed is False
        assert required == PlanName.PREMIUM


class TestEnforceFeature:
    async def test_below_threshold_raises_402_with_structure(self):
        svc = FeatureGatingService(_tenant_db(PlanType.FREEMIUM, _plan_row(PlanName.FREEMIUM)))

        with pytest.raises(FeatureRequiresPlanError) as exc_info:
            await svc.enforce_feature(uuid.uuid4(), "security")

        exc = exc_info.value
        assert exc.status_code == 402
        assert exc.extra["error"] == "feature_requires_plan"
        assert exc.extra["feature"] == "security"
        assert exc.extra["required_plan"] == "premium"
        assert exc.extra["upgrade_url"] == "/billing/plans"

    async def test_at_threshold_no_raise(self):
        svc = FeatureGatingService(_tenant_db(PlanType.PREMIUM, _plan_row(PlanName.PREMIUM)))
        await svc.enforce_feature(uuid.uuid4(), "security")  # nie rzuca


class TestConfigChangeWithoutDeploy:
    """AC7 — edycja ``gated_modules`` w features zmienia dostęp bez deployu."""

    async def test_threshold_edit_unlocks_module(self):
        edited = dict(GATED_MODULES)
        edited["security"] = "basic"  # próg obniżony w konfiguracji (DB)
        db = _tenant_db(PlanType.FREEMIUM, _plan_row(PlanName.FREEMIUM, {"gated_modules": edited}))

        assert await FeatureGatingService(db).has_feature(uuid.uuid4(), "security") is False

        db = _tenant_db(PlanType.BASIC, _plan_row(PlanName.BASIC, {"gated_modules": edited}))
        assert await FeatureGatingService(db).has_feature(uuid.uuid4(), "security") is True

    async def test_module_added_to_config_becomes_gated(self):
        edited = dict(GATED_MODULES)
        edited["new_module"] = "premium"
        db = _tenant_db(PlanType.BASIC, _plan_row(PlanName.BASIC, {"gated_modules": edited}))

        allowed, required = await FeatureGatingService(db).evaluate(uuid.uuid4(), "new_module")
        assert allowed is False
        assert required == PlanName.PREMIUM


class TestGetFeaturesStatus:
    async def test_freemium_locks_all_gated_modules(self):
        svc = FeatureGatingService(_tenant_db(PlanType.FREEMIUM, _plan_row(PlanName.FREEMIUM)))
        status = await svc.get_features_status(uuid.uuid4())

        assert status["current_plan"] == PlanType.FREEMIUM
        modules = {m["key"]: m for m in status["modules"]}
        for key in ("documentation", "uml", "gui", "integration_tests", "ci_cd"):
            assert modules[key]["locked"] is True
            assert modules[key]["required_plan"] == "basic"
        for key in ("security", "security_recommendations", "code_doc_consistency", "functional_gaps"):
            assert modules[key]["locked"] is True
            assert modules[key]["required_plan"] == "premium"
        assert modules["code_analysis"]["locked"] is False

    async def test_basic_unlocks_basic_modules_only(self):
        svc = FeatureGatingService(_tenant_db(PlanType.BASIC, _plan_row(PlanName.BASIC)))
        status = await svc.get_features_status(uuid.uuid4())

        modules = {m["key"]: m for m in status["modules"]}
        assert modules["documentation"]["locked"] is False
        assert modules["gui"]["locked"] is False
        assert modules["security"]["locked"] is True

    async def test_premium_unlocks_everything(self):
        svc = FeatureGatingService(_tenant_db(PlanType.PREMIUM, _plan_row(PlanName.PREMIUM)))
        status = await svc.get_features_status(uuid.uuid4())

        assert all(m["locked"] is False for m in status["modules"])


class TestRequireFeatureDependency:
    """Dep FastAPI — allow/deny bez rebuildu aplikacji."""

    async def test_denies_below_threshold(self):
        dep = require_feature("security")
        db = _tenant_db(PlanType.BASIC, _plan_row(PlanName.BASIC))

        with pytest.raises(FeatureRequiresPlanError):
            await dep(gate=FeatureGatingService(db), tenant_id=uuid.uuid4())

    async def test_allows_at_threshold(self):
        dep = require_feature("security")
        db = _tenant_db(PlanType.PREMIUM, _plan_row(PlanName.PREMIUM))

        result = await dep(gate=FeatureGatingService(db), tenant_id=uuid.uuid4())
        assert result is None
