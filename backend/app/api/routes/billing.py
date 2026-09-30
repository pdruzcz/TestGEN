"""Billing routes — Epic 7, Story 7.1 + 7.4.

GET /billing/plans — porównanie planów z aktualnym planem tenanta
+ linki prawne (regulamin/polityka) z konfiguracji — wymóg tpay dla
stron związanych z zakupami (nigdy hardcode w komponencie).

POST /billing/checkout (7.4 AC1) — inicjacja checkoutu redirect tpay.
GET /billing/transactions/{order_id} (7.4 AC2/AC7) — status transakcji
dla stron powrotu (polling) z jednorazowym fallbackiem reconciliation.
"""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_billing import get_billing_settings
from app.core.dependencies import get_current_user, get_db, get_payment_provider, require_role
from app.core.exceptions import ConflictError, NotFoundError
from app.models.payment import PaymentStatus, PaymentTransaction
from app.models.subscription_plan import PlanName
from app.models.tenant import Tenant
from app.models.usage import CounterType
from app.models.user import User
from app.schemas.billing import (
    CheckoutIn,
    CheckoutOut,
    FeaturesStatusOut,
    ForecastOut,
    InvoiceDataIn,
    InvoiceDataOut,
    InvoiceListOut,
    InvoiceOut,
    PaymentMethodOut,
    PaymentMethodRegistrationOut,
    PeriodOut,
    PlanChangeIn,
    PlanChangeOut,
    PlanChangeResultOut,
    PlanComparisonOut,
    PlanOut,
    ProrationOut,
    SubscriptionDetailOut,
    SubscriptionPaymentMethodOut,
    TransactionListOut,
    TransactionOut,
    TransactionStatusOut,
    UsageCounterOut,
    UsageDashboardOut,
    UsageEntryOut,
    UsageHistoryOut,
    UsageHistoryPointOut,
)
from app.services.billing.feature_gating import FeatureGatingService
from app.services.billing.invoice_service import InvoiceService
from app.services.billing.providers.base import PaymentProvider, ProviderTransaction
from app.services.billing.providers.tpay.client import TpayApiError
from app.services.billing.quota_service import QuotaService
from app.services.billing.subscription_service import SubscriptionDetail, SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

# Reconciliation fallback (AC7): nie odpytujemy tpay od razu — dopiero gdy
# transakcja lokalnie pending dłużej niż próg (płatnik wrócił przed webhookiem).
_RECONCILE_AFTER = timedelta(seconds=90)


def _tenant_of(current_user: User) -> uuid.UUID:
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="No tenant context")
    return tenant_id


def _detail_out(detail: SubscriptionDetail) -> SubscriptionDetailOut:
    """Złożenie SubscriptionDetailOut (AC3) z danych serwisu."""
    sub, plan = detail.subscription, detail.plan
    return SubscriptionDetailOut(
        id=sub.id,
        tenant_id=sub.tenant_id,
        plan_id=sub.plan_id,
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        next_charge_at=sub.next_charge_at,
        cancel_at_period_end=sub.cancel_at_period_end,
        trial_end=sub.trial_end,
        plan_name=plan.name if plan else None,
        plan_display_name=plan.display_name if plan else None,
        plan_price_monthly=plan.price_monthly if plan else None,
        plan_currency=plan.currency if plan else None,
        payment_method=(
            SubscriptionPaymentMethodOut.model_validate(detail.payment_method)
            if detail.payment_method is not None
            else None
        ),
        pending_change=(
            PlanChangeOut.model_validate(detail.pending_change) if detail.pending_change is not None else None
        ),
        grace_until=sub.grace_until,
    )


@router.get(
    "/plans",
    response_model=PlanComparisonOut,
    description=(
        "**Porównanie planów subskrypcji (Story 7.1).**\n\n"
        "Zwraca 3 plany (Freemium/Basic/Premium) z macierzą limitów `features`, "
        "aktualny plan tenanta (`current_plan`) oraz URL-e regulaminu i polityki "
        "prywatności (wymóg tpay dla stron zakupowych)."
    ),
)
async def get_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlanComparisonOut:
    tid = _tenant_of(current_user)
    svc = SubscriptionService(db)
    plans = await svc.get_plans()
    subscription = await svc.get_current_subscription(tid)

    plan_name_by_id = {plan.id: plan.name for plan in plans}
    if subscription:
        current_plan = plan_name_by_id.get(subscription.plan_id)
    else:
        # Plan startowy (Freemium) nie ma wiersza subskrypcji — fallback do
        # kolumny tenants.plan, żeby FE podświetlał aktualny plan (fix
        # 2026-09-14: bez tego current_plan=null i karta się nie wyróżnia).
        tenant_row = (await db.execute(select(Tenant).where(Tenant.id == tid))).scalar_one_or_none()
        current_plan = tenant_row.plan if tenant_row else None

    billing = get_billing_settings()
    return PlanComparisonOut(
        plans=[PlanOut.model_validate(p) for p in plans],
        current_plan=current_plan,
        terms_url=billing.billing_terms_url,
        privacy_policy_url=billing.billing_privacy_policy_url,
    )


@router.get(
    "/subscription",
    response_model=SubscriptionDetailOut,
    description=(
        "**Szczegóły subskrypcji (AC3, portal bilingowy).** Plan (nazwa, cena "
        "miesięczna), status, okres rozliczeniowy, metoda płatności "
        "(``card_tail``/``card_brand`` z PaymentToken albo BLIK), zaplanowany "
        "downgrade (7.5) i stan windykacji (``grace_until``)."
    ),
)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetailOut:
    tid = _tenant_of(current_user)
    detail = await SubscriptionService(db).get_subscription_details(tid)
    return _detail_out(detail)


@router.get(
    "/usage",
    response_model=dict[str, UsageEntryOut],
    description=(
        "Liczniki użycia tenanta z limitami planu i procentem wykorzystania "
        "(Story 7.8). Klucz = typ zasobu; `limit`/`percent` = null → unlimited."
    ),
)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, UsageEntryOut]:
    tid = _tenant_of(current_user)
    usage = await QuotaService(db).get_usage(tid)
    return {resource: UsageEntryOut(**entry) for resource, entry in usage.items()}


# --- Story 7.9: dashboard zużycia zasobów (AC1-AC5) ---


@router.get(
    "/usage/dashboard",
    response_model=UsageDashboardOut,
    description=(
        "**Dashboard zużycia zasobów (Story 7.9, AC5).** Okres rozliczeniowy, "
        "plan, karty zasobów (4 typy — bez `users`, CR#2; `limit`/`percentage` "
        "= null → unlimited), prognoza limitu analiz (opcjonalna, ≥ 7 dni "
        "danych, AC4) i liczba dni do końca okresu."
    ),
)
async def get_usage_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageDashboardOut:
    tid = _tenant_of(current_user)
    data = await QuotaService(db).get_dashboard_data(tid)
    return UsageDashboardOut(
        current_period=PeriodOut(start=data.current_period_start, end=data.current_period_end),
        plan=data.plan,
        counters=[
            UsageCounterOut(
                type=c.counter_type.value,
                value=c.value,
                limit=c.limit,
                percentage=c.percentage,
            )
            for c in data.counters
        ],
        forecast=(
            ForecastOut(
                counter_type=data.forecast.counter_type.value,
                limit_date=data.forecast.limit_date,
                avg_daily=data.forecast.avg_daily,
                days_to_limit=data.forecast.days_to_limit,
                exceeds_before_period_end=data.forecast.exceeds_before_period_end,
            )
            if data.forecast is not None
            else None
        ),
        days_remaining=data.days_remaining,
    )


@router.get(
    "/usage/history",
    response_model=UsageHistoryOut,
    description=(
        "**Historia zużycia zasobu (Story 7.9, AC3).** Daily snapshoty "
        "(`usage_history`) rosnąco po dacie — dane wykresu liniowego "
        "zużycia skumulowanego. `counter_type` ∈ {analyses, test_cases, "
        "storage_bytes, files_per_analysis}; `days` 1-90 (domyślnie 30)."
    ),
)
async def get_usage_history(
    counter_type: CounterType = Query(...),
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageHistoryOut:
    tid = _tenant_of(current_user)
    points = await QuotaService(db).get_usage_history(tid, counter_type, days=days)
    return UsageHistoryOut(
        counter_type=counter_type.value,
        days=days,
        points=[UsageHistoryPointOut(date=p.date, value=p.value) for p in points],
    )


@router.get(
    "/features",
    response_model=FeaturesStatusOut,
    description=(
        "**Status modułów gated (Story 7.13, FR71).** Wzorzec "
        "„widoczne-zablokowane”: każdy moduł ma `locked` + `required_plan` "
        "(tylko gdy zablokowany) wg progu z `subscription_plans.features"
        ".gated_modules`. Plan tenanta z `tenants.plan` (sync z subskrypcją)."
    ),
)
async def get_features_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeaturesStatusOut:
    tid = _tenant_of(current_user)
    status = await FeatureGatingService(db).get_features_status(tid)
    return FeaturesStatusOut(**status)


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    status_code=200,
    description=(
        "**Inicjacja checkoutu tpay (Story 7.4, AC1).**\n\n"
        "Wymaga roli **Owner** (403 inaczej). Tworzy `PaymentTransaction` "
        "(pending) z `hidden_description` = `order_id` (UUID — korelacja "
        "webhooka po `tr_crc`), wysyła `POST {TPAY_BASE_URL}/transactions` "
        "i zwraca URL Panelu Transakcyjnego (BLIK/PBL/karta z 3DS). "
        "Jedyny cykl: **miesięczny** (30/50 PLN z env). Aktywny plan płatny "
        "→ 409 (zmiana planu przez `/subscription/change`, Story 7.5)."
    ),
)
async def create_checkout(
    body: CheckoutIn,
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> CheckoutOut:
    tid = _tenant_of(current_user)

    # AC1: tenant z aktywnym planem płatnym → 409 (zmiana planu: 7.5).
    svc = SubscriptionService(db)
    active_paid = await svc.get_active_paid_plan_name(tid)
    if active_paid is not None:
        raise ConflictError(f"Aktywna subskrypcja planu {active_paid.value} — zmiana planu przez /subscription/change")

    billing = get_billing_settings()
    plan = body.plan
    amount = billing.billing_basic_monthly_price if plan == PlanName.BASIC else billing.billing_premium_monthly_price

    order_id = str(uuid.uuid4())
    # Wartość aliasu BLIK generowana przez merchanta (7.3 AC3): checkout
    # przekazuje ją w ``blikPaymentData.aliases[0].value`` i zapisuje w meta —
    # notyfikacje ``ALIAS_*`` korelują tenant dokładnie po tej wartości.
    blik_alias_value = f"tg-{uuid.uuid4().hex}"
    txn = PaymentTransaction(
        tenant_id=tid,
        provider="tpay",
        hidden_description=order_id,
        amount=amount,
        currency=billing.billing_currency,
        status=PaymentStatus.PENDING,
        meta={
            "plan": plan,
            "payer_email": current_user.email,
            "payer_name": current_user.name,
            "blik_alias_value": blik_alias_value,
        },
    )
    db.add(txn)
    await db.flush()

    try:
        checkout = await provider.create_checkout(
            amount=amount,
            currency=billing.billing_currency,
            description=f"TestGEN — subskrypcja {plan.capitalize()} (miesięczna)",
            order_id=order_id,
            payer_email=current_user.email,
            payer_name=current_user.name,
            blik_alias_value=blik_alias_value,
        )
    except TpayApiError as exc:
        await db.rollback()
        if "refusenopayid" in str(exc).lower():
            # 7.2 AC7: bank płatnika nie obsługuje Płatności Powtarzalnych
            # BLIK — komunikat z sugestią zapisu karty (metoda z AC2).
            raise HTTPException(
                status_code=422,
                detail=(
                    "Twój bank nie obsługuje płatności powtarzalnych BLIK "
                    "(Płatności Powtarzalne). Zapłać kartą i zapisz ją jako "
                    "metodę płatności, aby odnowienia następowały automatycznie."
                ),
            ) from None
        logger.exception("tpay create_checkout nie powiódł się (order %s)", order_id)
        raise HTTPException(
            status_code=502,
            detail="Payment provider error — spróbuj ponownie za chwilę",
        ) from None
    except Exception:
        # Transakcja nigdy nie powstała u tpay — cofamy lokalny rekord pending.
        await db.rollback()
        logger.exception("tpay create_checkout nie powiódł się (order %s)", order_id)
        raise HTTPException(
            status_code=502,
            detail="Payment provider error — spróbuj ponownie za chwilę",
        ) from None

    txn.transaction_id = checkout.transaction_id
    await db.commit()

    logger.info("Checkout %s: tenant=%s plan=%s txn=%s", order_id, tid, plan, checkout.transaction_id)
    return CheckoutOut(
        order_id=order_id,
        transaction_id=checkout.transaction_id,
        transaction_payment_url=checkout.transaction_payment_url,
        plan=plan,
        amount=amount,
        currency=billing.billing_currency,
    )


@router.get(
    "/transactions/{order_id}",
    response_model=TransactionStatusOut,
    description=(
        "**Status transakcji (Story 7.4, AC2/AC7).** Polling stron powrotu. "
        "Gdy lokalnie `pending` dłużej niż próg — **jednorazowy** fallback "
        "reconciliation `GET /transactions/{id}` u tpay (okresowy polling "
        "wzbroniony — wymóg tpay). Rozbieżności logowane jako alerty."
    ),
)
async def get_transaction_status(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> TransactionStatusOut:
    tid = _tenant_of(current_user)

    result = await db.execute(select(PaymentTransaction).where(PaymentTransaction.hidden_description == order_id))
    txn = result.scalar_one_or_none()
    if txn is None or txn.tenant_id != tid:
        raise NotFoundError("Transaction not found")

    # Reconciliation fallback (AC7) — tylko dla pending po progiem czasu.
    if txn.status == PaymentStatus.PENDING and txn.transaction_id:
        created = txn.created_at or datetime.now(UTC)
        if datetime.now(UTC) - created > _RECONCILE_AFTER:
            try:
                remote = await provider.get_transaction(txn.transaction_id)
            except Exception:
                logger.exception("Reconciliation tpay nie powiodła się (order %s)", order_id)
            else:
                await _reconcile(db, provider, txn, remote)
                await db.commit()

    plan_raw = (txn.meta or {}).get("plan")
    return TransactionStatusOut(
        order_id=order_id,
        status=txn.status,
        plan=PlanName(plan_raw) if plan_raw else None,
        amount=txn.amount,
        currency=txn.currency,
        test_mode=txn.test_mode,
    )


async def _reconcile(
    db: AsyncSession, provider: PaymentProvider, txn: PaymentTransaction, remote: ProviderTransaction
) -> None:
    """Zdarzeniowy fallback (AC7) — nie polling. Rozbieżności → alerty."""
    from app.services.billing.providers.tpay.transactions import is_paid
    from app.services.billing.webhook_processor import WebhookProcessor

    if is_paid(remote.status):
        if remote.amount != txn.amount:
            logger.error(
                "RECONCILE ALERT order %s: kwota u tpay %s != lokalna %s — ręczna weryfikacja",
                txn.hidden_description,
                remote.amount,
                txn.amount,
            )
            return
        txn.test_mode = remote.test_mode
        txn.paid_amount = remote.paid_amount or txn.amount
        await WebhookProcessor(db, provider).mark_paid(txn)
        logger.info("RECONCILE order %s: oznaczono paid po fallbacku tpay", txn.hidden_description)
    elif txn.status != PaymentStatus.PENDING:
        logger.error(
            "RECONCILE ALERT order %s: lokalnie %s, u tpay %s — rozbieżność stanów",
            txn.hidden_description,
            txn.status.value,
            remote.status,
        )


# --- Story 7.2: metody płatności (AC2/AC3) ---


@router.get(
    "/payment-methods",
    response_model=list[PaymentMethodOut],
    description=(
        "**Metody płatności tenanta (Story 7.2 AC3 + 7.7 AC1).** Karta "
        "(`card_token`) lub BLIK (`blik_alias_payid`): `card_tail`/`card_brand`, "
        "status (pending = rejestracja w toku), informacja o metodzie domyślnej. "
        "Wymaga roli **Owner**. Karty odświeżane u tpay przez `GET /tokens/{value}` "
        "z krótkoterminowym cache'em (dryf statusu/wizerunku zapisywany lokalnie; "
        "błąd dostawcy → stan lokalny)."
    ),
)
async def list_payment_methods(
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> list[PaymentMethodOut]:
    tid = _tenant_of(current_user)
    methods, changed = await SubscriptionService(db).refresh_payment_method_statuses(tid, provider=provider)
    if changed:
        await db.commit()
    return [PaymentMethodOut.model_validate(m) for m in methods]


@router.post(
    "/payment-methods",
    response_model=PaymentMethodRegistrationOut,
    status_code=200,
    description=(
        "**Dodaj kartę — rejestracja bez obciążenia (Story 7.2, AC2).** "
        "Tworzy rekord `PaymentToken` (pending) i rejestrację tokena "
        "`POST {TPAY_BASE_URL}/tokens` z `cliAuth` = registration_id; "
        "zwraca URL przekierowania na panel tpay. Po powrocie płatnika tpay "
        "wysyła notyfikację JSON `data.token` → token przechodzi w `active` "
        "(potwierdzenie — handler notyfikacji, Story 7.3)."
    ),
)
async def register_payment_method(
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> PaymentMethodRegistrationOut:
    tid = _tenant_of(current_user)

    registration_id = uuid.uuid4().hex
    svc = SubscriptionService(db)
    token = await svc.create_pending_registration(tid, registration_id=registration_id)
    await db.flush()

    billing = get_billing_settings()
    try:
        registration = await provider.register_card_token(
            callback_url=billing.tpay_payment_methods_return_url,
            cli_auth=registration_id,
        )
    except Exception:
        await db.rollback()
        logger.exception("tpay register_token nie powiódł się (tenant %s)", tid)
        raise HTTPException(
            status_code=502,
            detail="Payment provider error — spróbuj ponownie za chwilę",
        ) from None

    await db.commit()
    logger.info("Rejestracja karty %s: tenant=%s url=%s", registration_id, tid, registration.transaction_payment_url)
    return PaymentMethodRegistrationOut(
        token_id=token.id,
        registration_url=registration.transaction_payment_url,
    )


@router.delete(
    "/payment-methods/{token_id}",
    response_model=PaymentMethodOut,
    description=(
        "**Usunięcie metody płatności (Story 7.2, AC3).** Woła "
        "`DELETE {TPAY_BASE_URL}/tokens/{value}` u tpay i lokalnie ustawia "
        "`tpay_status = deleted` (soft delete). Usunięcie jedynej aktywnej "
        "metody przy aktywnej subskrypcji cyklicznej → **409** (najpierw "
        "dodaj inną metodę)."
    ),
)
async def delete_payment_method(
    token_id: uuid.UUID,
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> PaymentMethodOut:
    tid = _tenant_of(current_user)
    svc = SubscriptionService(db)

    # Najpierw u tpay (błąd → 502, lokalnie nic się nie zmienia)…
    token = await svc.get_payment_method(tid, token_id)
    value = await svc.get_token_value(token)
    try:
        await provider.delete_token(value)
    except Exception:
        logger.exception("tpay delete_token nie powiódł się (token %s, tenant %s)", token_id, tid)
        raise HTTPException(
            status_code=502,
            detail="Payment provider error — spróbuj ponownie za chwilę",
        ) from None

    # …potem lokalny soft delete (może rzucić 409 na ostatnią metodę).
    deleted = await svc.delete_payment_method(tid, token_id, token=token)
    await db.commit()
    return PaymentMethodOut.model_validate(deleted)


# --- Story 7.5: upgrade/downgrade planu z prorated billing (AC1-AC5) ---


@router.post(
    "/subscription/change",
    response_model=PlanChangeResultOut,
    status_code=200,
    description=(
        "**Zmiana planu (Story 7.5, AC1/AC2).** Wymaga roli **Owner**.\n\n"
        "Upgrade: obciążenie prorated (zapisana metoda 7.2 — bez redirectu; "
        "inaczej checkout tpay z `payment_url`), plan zmieniany po webhooku "
        "`paid`; kwota ≤ 0,00 → zmiana natychmiast bez obciążenia. "
        "Downgrade: czysto lokalnie — `cancel_at_period_end`, efektywny na "
        "koniec okresu (bez wywołań tpay, bez zwrotów).\n\n"
        "Błędy: ten sam plan → **400**; downgrade w trakcie dunningu → **409**."
    ),
)
async def change_subscription_plan(
    body: PlanChangeIn,
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
    provider: PaymentProvider = Depends(get_payment_provider),
) -> PlanChangeResultOut:
    tid = _tenant_of(current_user)
    svc = SubscriptionService(db)
    try:
        result = await svc.change_plan(
            tid,
            body.plan,
            current_user.id,
            provider=provider,
            owner_email=current_user.email,
            owner_name=current_user.name,
        )
    except ValueError as exc:
        # Task 3.2: zmiana na ten sam plan → 400.
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except (ConflictError, NotFoundError):
        raise
    except Exception:
        await db.rollback()
        logger.exception("Zmiana planu nie powiodła się (tenant %s → %s)", tid, body.plan)
        raise HTTPException(
            status_code=502,
            detail="Payment provider error — spróbuj ponownie za chwilę",
        ) from None

    await db.commit()
    return PlanChangeResultOut(
        change=PlanChangeOut.model_validate(result.change),
        change_type=result.change_type,
        amount=result.amount,
        currency=get_billing_settings().billing_currency,
        payment_required=result.payment_required,
        payment_url=result.payment_url,
        order_id=result.order_id,
    )


@router.post(
    "/subscription/change/cancel-pending",
    response_model=PlanChangeOut,
    status_code=200,
    description=(
        "**Rezygnacja z zaplanowanego downgrade (Story 7.5, AC3).** "
        "Wymaga roli **Owner**. Bez wywołań tpay: rekord `canceled`, "
        "`cancel_at_period_end = false`, przywrócone `next_charge_at`. "
        "Brak oczekującej zmiany → **404**."
    ),
)
async def cancel_pending_plan_change(
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> PlanChangeOut:
    tid = _tenant_of(current_user)
    canceled = await SubscriptionService(db).cancel_pending_change(tid)
    await db.commit()
    return PlanChangeOut.model_validate(canceled)


@router.get(
    "/subscription/history",
    response_model=list[PlanChangeOut],
    description=(
        "**Historia zmian planu (Story 7.5, AC4).** Wymaga roli **Owner**. "
        "Rekordy audytowe (upgrade/downgrade, status, proration) — najnowsze pierwsze."
    ),
)
async def get_plan_change_history(
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> list[PlanChangeOut]:
    tid = _tenant_of(current_user)
    history = await SubscriptionService(db).get_change_history(tid)
    return [PlanChangeOut.model_validate(h) for h in history]


@router.get(
    "/subscription/proration",
    response_model=ProrationOut,
    description=(
        "**Podgląd proration (Story 7.5, AC5).** Wymaga roli **Owner**. "
        "Kwota liczona lokalnie (D2 — bez API tpay) wg tych samych wejść co "
        "obciążenie: `((cena_nowego/dni_okresu) - (cena_starego/dni_okresu)) "
        "x pozostałe_dni`. Downgrade → 0,00. Ten sam plan → **400**."
    ),
)
async def preview_plan_proration(
    plan: PlanName,
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> ProrationOut:
    tid = _tenant_of(current_user)
    try:
        details = await SubscriptionService(db).preview_proration(tid, plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return ProrationOut(**details)


# --- Story 7.7: portal billingowy (AC2-AC5) ---


@router.get(
    "/transactions",
    response_model=TransactionListOut,
    description=(
        "**Historia transakcji (Story 7.7, AC2).** Malejąco po dacie; filtry: "
        "`status` (pending|paid|charged_back|refunded), `date_from`/`date_to` "
        "(włącznie); paginacja — domyślnie 20/stronę. Metoda płatności z faktury "
        "(karta/BLIK/przelew) lub BLIK po aliasie z meta; powiązana faktura "
        "(numer + id, do pobrania PDF z `/billing/invoices`). Dostępne dla "
        "Ownera i Usera (przeglądanie); RLS — tenant widzi tylko swoje transakcje."
    ),
)
async def list_transactions(
    status: PaymentStatus | None = Query(None, description="Filtr po statusie"),
    date_from: date | None = Query(None, description="Początek zakresu dat (włącznie)"),
    date_to: date | None = Query(None, description="Koniec zakresu dat (włącznie)"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionListOut:
    tid = _tenant_of(current_user)
    items, total = await SubscriptionService(db).get_transactions(
        tid, status=status, date_from=date_from, date_to=date_to, page=page, size=size
    )
    return TransactionListOut(
        items=[
            TransactionOut(
                id=item.transaction.id,
                created_at=item.transaction.created_at,
                amount=item.transaction.amount,
                currency=item.transaction.currency,
                status=item.transaction.status,
                paid_amount=item.transaction.paid_amount,
                method=item.method,
                transaction_id=item.transaction.transaction_id,
                order_id=item.transaction.hidden_description,
                invoice_id=item.invoice.id if item.invoice is not None else None,
                invoice_number=item.invoice.invoice_number if item.invoice is not None else None,
                test_mode=item.transaction.test_mode,
            )
            for item in items
        ],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/subscription/cancel",
    response_model=SubscriptionDetailOut,
    description=(
        "**Anulowanie subskrypcji (Story 7.7, AC4).** Operacja lokalna (§3.5 "
        "planu tpay) — **bez wywołania API tpay**: `cancel_at_period_end = true`, "
        "zatrzymane `next_charge_at`. Dostęp utrzymany do końca okresu, potem "
        "automatyczny powrót do Freemium (lub planu z zaplanowanego downgrade'u "
        "7.5). Wymaga roli **Owner**; Freemium → 409; już anulowana → 409."
    ),
)
async def cancel_subscription(
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetailOut:
    tid = _tenant_of(current_user)
    svc = SubscriptionService(db)
    await svc.cancel_subscription(tid)
    await db.commit()
    return _detail_out(await svc.get_subscription_details(tid))


@router.post(
    "/subscription/reactivate",
    response_model=SubscriptionDetailOut,
    description=(
        "**Reaktywacja anulowanej subskrypcji (Story 7.7, AC5).** Lokalnie "
        "(bez API tpay): zdjęcie `cancel_at_period_end`, przywrócone "
        "`next_charge_at` = koniec bieżącego okresu — kontynuacja bez przerwy. "
        "Wymaga roli **Owner**; sprzeczna z zaplanowaną zmianą planu → 409."
    ),
)
async def reactivate_subscription(
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetailOut:
    tid = _tenant_of(current_user)
    svc = SubscriptionService(db)
    await svc.reactivate_subscription(tid)
    await db.commit()
    return _detail_out(await svc.get_subscription_details(tid))


# --- Story 7.6: faktury VAT (AC4/AC5) ---


@router.get(
    "/invoices",
    response_model=InvoiceListOut,
    description=(
        "**Lista faktur VAT (Story 7.6, AC5).** Owner lub User. Malejąco po "
        "dacie wystawienia; paginacja domyślnie 20/stronę (`page`, `size`)."
    ),
)
async def list_invoices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceListOut:
    tid = _tenant_of(current_user)
    invoices, total = await InvoiceService(db).get_invoices(tid, page=page, size=size)
    return InvoiceListOut(
        items=[InvoiceOut.model_validate(i) for i in invoices],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/invoices/{invoice_id}/pdf",
    response_class=Response,
    description=(
        "**Pobranie PDF faktury (Story 7.6, AC5).** Owner lub User; plik z "
        "MinIO. **404** gdy PDF jeszcze nie wygenerowany (asynchronicznie z "
        "Celery po płatności) lub faktura nie należy do tenanta."
    ),
)
async def download_invoice_pdf(
    invoice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    tid = _tenant_of(current_user)
    invoice, pdf_bytes = await InvoiceService(db).get_invoice_pdf(invoice_id, tid)
    filename = f"Faktura_{invoice.invoice_number.replace('/', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/invoice-data",
    response_model=InvoiceDataOut,
    description=(
        "**Dane fakturowe tenanta (Story 7.6, AC4).** Wymaga roli **Owner**. "
        "Brak rekordu → inicjalizacja z profilu tenanta (nazwa, NIP)."
    ),
)
async def get_invoice_data(
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> InvoiceDataOut:
    tid = _tenant_of(current_user)
    data = await InvoiceService(db).get_or_create_invoice_data(tid)
    await db.commit()
    return InvoiceDataOut.model_validate(data)


@router.put(
    "/invoice-data",
    response_model=InvoiceDataOut,
    description=(
        "**Aktualizacja danych fakturowych (Story 7.6, AC4).** Wymaga roli "
        "**Owner**. Zmiana dotyczy wyłącznie **następnych** faktur — już "
        "wystawione trzymają snapshot danych z chwili wystawienia."
    ),
)
async def update_invoice_data(
    body: InvoiceDataIn,
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
) -> InvoiceDataOut:
    tid = _tenant_of(current_user)
    data = await InvoiceService(db).update_invoice_data(
        tid,
        company_name=body.company_name,
        nip=body.nip,
        address={
            "street": body.street,
            "city": body.city,
            "postal_code": body.postal_code,
            "country": body.country,
        },
    )
    await db.commit()
    return InvoiceDataOut.model_validate(data)
