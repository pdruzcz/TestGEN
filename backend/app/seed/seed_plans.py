"""Seed definicji planów subskrypcji — Story 7.1 (AC5).

Idempotentny upsert: brakujące plany tworzy, istniejące aktualizuje
ceną z env. Uruchamiany w startup hooku — wymiana cen = zmiana env +
restart, bez deployu kodu.
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_billing import BillingSettings, get_billing_settings
from app.models.subscription_plan import PlanName, SubscriptionPlan

logger = logging.getLogger(__name__)

MB = 1024 * 1024
GB = 1024 * 1024 * 1024

# Progi modułów gated (komplet zatwierdzony 2026-08-28, egzekwowane w 7.13):
# kod + TC = wszyscy; dokumentacja/UML/GUI/testy integracyjne + CI/CD = basic;
# bezpieczeństwo + rekomendacje, kod↔dok, luki funkcjonalne = premium.
GATED_MODULES: dict[str, str] = {
    "code_analysis": "freemium",
    "test_generation": "freemium",
    "documentation": "basic",
    "uml": "basic",
    "gui": "basic",
    "integration_tests": "basic",
    "ci_cd": "basic",
    "security": "premium",
    "security_recommendations": "premium",
    "code_doc_consistency": "premium",
    "functional_gaps": "premium",
}

# Macierz limitów — komplet zatwierdzony 2026-08-28. None = unlimited.
PLAN_FEATURES: dict[PlanName, dict] = {
    PlanName.FREEMIUM: {
        "analyses": 10,
        "test_cases": 50,
        "storage_bytes": 500 * MB,
        "files_per_analysis": 5,
        "rate_limit_per_min": 100,
        "projects": None,  # unlimited — wymiar informatywny (kandydat do usunięcia)
        "llm_cost_tracking": False,  # 7.10 usunięte — wyłączony we wszystkich planach
        "priority_support": False,
        "gated_modules": dict(GATED_MODULES),
    },
    PlanName.BASIC: {
        "analyses": 50,
        "test_cases": 250,
        "storage_bytes": 5 * GB,
        "files_per_analysis": 25,
        "rate_limit_per_min": 100,
        "projects": None,
        "llm_cost_tracking": False,
        "priority_support": False,
        "gated_modules": dict(GATED_MODULES),
    },
    PlanName.PREMIUM: {
        "analyses": None,  # unlimited
        "test_cases": None,
        "storage_bytes": 10 * GB,
        "files_per_analysis": 50,
        "rate_limit_per_min": 1000,
        "projects": None,
        "llm_cost_tracking": False,
        "priority_support": True,
        "gated_modules": dict(GATED_MODULES),
    },
}


async def seed_subscription_plans(
    db: AsyncSession,
    settings: BillingSettings | None = None,
) -> list[SubscriptionPlan]:
    """Upsert 3 planów (Freemium/Basic/Premium) — idempotentny re-seed.

    Freemium zawsze 0; Basic/Premium z env. ``features`` (macierz limitów)
    i pozostałe pola opisowe są odświeżane — jedno źródło prawdy w DB.
    """
    billing = settings or get_billing_settings()

    prices: dict[PlanName, Decimal] = {
        PlanName.FREEMIUM: Decimal("0.00"),
        PlanName.BASIC: billing.billing_basic_monthly_price,
        PlanName.PREMIUM: billing.billing_premium_monthly_price,
    }

    result = await db.execute(select(SubscriptionPlan))
    existing = {plan.name: plan for plan in result.scalars().all()}

    seeded: list[SubscriptionPlan] = []
    for sort_order, name in enumerate((PlanName.FREEMIUM, PlanName.BASIC, PlanName.PREMIUM)):
        plan = existing.get(name)
        if plan is None:
            plan = SubscriptionPlan(name=name)
            db.add(plan)
            logger.info("Seeding subscription plan %s (%s PLN/mies.)", name.value, prices[name])
        plan.display_name = name.value.capitalize()
        plan.price_monthly = prices[name]
        plan.currency = billing.billing_currency
        plan.features = PLAN_FEATURES[name]
        plan.is_active = True
        plan.sort_order = sort_order
        seeded.append(plan)

    await db.flush()

    # Jedno źródło prawdy: zasil cache limitów QuotaService z features (DB).
    from app.services.quota_service import set_plan_limits_cache

    set_plan_limits_cache({plan.name: plan.features.get("analyses") for plan in seeded})

    # Progi rate limitu per plan (Story 7.8, AC2) — też z features (DB).
    from app.middleware.rate_limit import set_rate_limits_cache

    set_rate_limits_cache({plan.name.value: plan.features.get("rate_limit_per_min") for plan in seeded})

    return seeded
