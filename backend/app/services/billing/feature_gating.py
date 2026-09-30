"""FeatureGatingService — dostęp do modułów per plan (Story 7.13, FR71).

Wzorzec „widoczne-zablokowane" (wniosek FEPW): moduły gated są widoczne
w UI, ale ich uruchomienie wymaga planu ≥ progu. Próg per moduł pochodzi
z ``subscription_plans.features.gated_modules`` (seed 7.1 — jedno źródło
prawdy; edycja progu w DB zmienia dostęp bez deployu).

Plan efektywny dla gatingu: legacy ``tenants.plan`` — kolumna trzymana
w sync z subskrypcją przez SubscriptionService (aktywacja/odnowienie/
downgrade). W grace po downgrade (dunning 7.2) zostaje na planie płatnym,
po wygaśnięciu grace przechodzi na Freemium — patrz
``_apply_dunning_downgrade`` / ``enforce_grace_expiry``.

Egzekwowanie: ``require_feature(module)`` — FastAPI dependency rzucająca
402 ``feature_requires_plan`` (wzorzec ``enforce_quota`` z 7.8).
"""

import logging
import uuid
from collections.abc import Callable

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_tenant
from app.core.exceptions import FeatureRequiresPlanError
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.tenant import PlanType, Tenant
from app.services.billing.subscription_service import PLAN_HIERARCHY

logger = logging.getLogger(__name__)

# CTA upgrade — strona planów (wzorzec QuotaExceededError, 7.8).
UPGRADE_URL = "/billing/plans"


def _as_plan_name(value: PlanType | PlanName | str | None) -> PlanName:
    """PlanType/str → PlanName (aliasy tego samego enuma, 7.1/2b.1)."""
    if value is None:
        return PlanName.FREEMIUM
    if isinstance(value, PlanName):
        return value
    return PlanName(value.value if isinstance(value, PlanType) else value)


class FeatureGatingService:
    """Sprawdzanie dostępu do modułów gated per plan (Story 7.13)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _tenant_plan_name(self, tenant_id: uuid.UUID) -> PlanName:
        """Plan tenanta z legacy ``tenants.plan`` (sync z subskrypcją)."""
        result = await self._db.execute(select(Tenant.plan).where(Tenant.id == tenant_id))
        plan = result.scalar_one_or_none()
        return _as_plan_name(plan)

    async def _gated_modules(self, plan_name: PlanName) -> dict[str, str]:
        """Mapa ``{moduł: wymagany plan}`` z ``features`` planu w DB."""
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name))
        plan = result.scalar_one_or_none()
        modules = (plan.features or {}).get("gated_modules", {}) if plan is not None else {}
        return {str(k): str(v) for k, v in dict(modules).items()}

    async def evaluate(self, tenant_id: uuid.UUID, module: str) -> tuple[bool, PlanName | None]:
        """``(allowed, required_plan)`` — hierarchia Freemium < Basic < Premium."""
        plan_name = await self._tenant_plan_name(tenant_id)
        required_raw = (await self._gated_modules(plan_name)).get(module)
        if required_raw is None:
            return True, None  # moduł niegated
        required = _as_plan_name(required_raw)
        return PLAN_HIERARCHY[plan_name] >= PLAN_HIERARCHY[required], required

    async def has_feature(self, tenant_id: uuid.UUID, module: str) -> bool:
        """Czy tenant ma dostęp do modułu (bez egzekwowania)."""
        allowed, _ = await self.evaluate(tenant_id, module)
        return allowed

    async def required_plan_for(self, tenant_id: uuid.UUID, module: str) -> PlanName | None:
        """Wymagany plan modułu z konfiguracji; ``None`` = moduł niegated."""
        _, required = await self.evaluate(tenant_id, module)
        return required

    async def enforce_feature(self, tenant_id: uuid.UUID, module: str) -> None:
        """402 ``feature_requires_plan`` gdy plan tenanta < próg modułu."""
        allowed, required = await self.evaluate(tenant_id, module)
        if allowed or required is None:
            return
        raise FeatureRequiresPlanError(
            detail=f"Funkcja jest dostępna w planie {required.value.capitalize()} — ulepsz subskrypcję, aby ją odblokować",
            error="feature_requires_plan",
            feature=module,
            required_plan=required.value,
            upgrade_url=UPGRADE_URL,
        )

    async def get_features_status(self, tenant_id: uuid.UUID) -> dict:
        """Status modułów dla FE (GET /billing/features): per moduł
        ``locked`` + ``required_plan`` (tylko gdy zablokowany)."""
        plan_name = await self._tenant_plan_name(tenant_id)
        modules = await self._gated_modules(plan_name)

        entries: list[dict] = []
        for key in sorted(modules):
            required = _as_plan_name(modules[key])
            locked = PLAN_HIERARCHY[plan_name] < PLAN_HIERARCHY[required]
            entries.append(
                {
                    "key": key,
                    "locked": locked,
                    "required_plan": required.value if locked else None,
                }
            )
        return {"current_plan": plan_name, "modules": entries}


async def get_feature_gate_service(db: AsyncSession = Depends(get_db)) -> FeatureGatingService:
    """Injectable fabryka serwisu (wzorzec ``get_quota_service``) — jeden
    punkt nadpisywania w testach (``dependency_overrides``)."""
    return FeatureGatingService(db)


def require_feature(module: str) -> Callable:
    """FastAPI dependency — 402 gdy plan tenanta poniżej progu modułu.

    Użycie: ``dependencies=[Depends(require_feature("security"))]`` na
    endpointach uruchamiających moduły gated (widoczne-zablokowane w UI).
    Tenant z ``get_tenant`` (request.state — wspólny źródło dla rout).
    """

    async def _dep(
        gate: FeatureGatingService = Depends(get_feature_gate_service),
        tenant_id: uuid.UUID = Depends(get_tenant),
    ) -> None:
        await gate.enforce_feature(tenant_id, module)

    return _dep
