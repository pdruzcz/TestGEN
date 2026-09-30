"""Fixtures scenariuszy billingowych — Story 7.12 (Task 1.2).

Harness testów scenariuszowych (``tests/scenarios/``): plany z seeda 7.1
(jedno źródło prawdy — ``PLAN_FEATURES``), subskrypcje/transakcje/tokeny,
mock sesji DB z sekwencją wyników ``execute`` (wzorzec testów API billingowych
7.4/7.2), provider tpay z przypiętym certyfikatem testowym oraz konteksty
wyłączające maile i pipeline faktur (asercje na mockach — w sandboxie maile
do płatników są zablokowane, §4.4 planu tpay).

Mock czasu: ``SubscriptionScheduler.run(now=...)`` przyjmuje chwilę wprost
(seam testowy 7.2), a progi dunningu/grace ustawia się na obiektach —
freezegun niepotrzebny (bez nowej zależności).
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.payment import (
    PaymentStatus,
    PaymentToken,
    PaymentTransaction,
    TokenKind,
    TpayTokenStatus,
)
from app.models.plan_change import PlanChangeHistory, PlanChangeStatus, PlanChangeType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.seed.seed_plans import PLAN_FEATURES
from app.services.billing.providers.tpay import TpayProvider
from app.services.billing.subscription_service import encrypt_token_value, token_digest
from tests.factories import make_user
from tests.fixtures.tpay_fixtures import (
    make_test_billing_settings,
    sign_jws,
    signing_cert_pem,
)

# --- Czas (mocki czasu dla schedulerów — Task 1.2) ---


def now_utc() -> datetime:
    return datetime.now(UTC)


def in_days(days: float, *, from_now: datetime | None = None) -> datetime:
    return (from_now or now_utc()) + timedelta(days=days)


def hours_later(hours: float, *, from_now: datetime | None = None) -> datetime:
    return (from_now or now_utc()) + timedelta(hours=hours)


# --- Wspólne moki wyników ``db.execute`` (wzorzec _scalar z testów API) ---


def scalar(item):
    """Wynik ``execute`` → ``scalar_one_or_none()`` zwraca ``item``."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


def scalars(*items):
    """Wynik ``execute`` → ``scalars().all()`` zwraca listę ``items``."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(items)
    return result


def savepoint_cm() -> MagicMock:
    """Async-CM dla ``db.begin_nested()`` (savepoint) na mockach —
    ``AsyncMock`` zwróciłby korutynę, nie context managera."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=cm)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def make_mock_db(*execute_results):
    """Sesja DB (AsyncMock) z kolejką wyników ``execute`` (sekwencja zapytań)."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=list(execute_results))
    db.begin_nested = MagicMock(return_value=savepoint_cm())
    return db


def added_objects(db) -> list:
    """Obiekty przekazane do ``db.add`` (w kolejności)."""
    return [call.args[0] for call in db.add.call_args_list]


# --- Plany (macierz limitów z seeda 7.1 — jedno źródło prawdy) ---


def make_plan(name: PlanName, *, price: str | None = None) -> SubscriptionPlan:
    prices = {"freemium": "0.00", "basic": "30.00", "premium": "50.00"}
    return SubscriptionPlan(
        id=uuid.uuid4(),
        name=name,
        display_name=name.value.capitalize(),
        price_monthly=Decimal(price or prices[name.value]),
        currency="PLN",
        features=dict(PLAN_FEATURES[name]),
        is_active=True,
        sort_order={"freemium": 0, "basic": 1, "premium": 2}[name.value],
    )


def make_plans() -> dict[PlanName, SubscriptionPlan]:
    """Trzy plany seeda: Freemium/Basic/Premium (tenant startowy = Freemium)."""
    return {name: make_plan(name) for name in PlanName}


# --- Obiekty domenowe ---


def make_subscription(
    plan: SubscriptionPlan,
    tenant_id: uuid.UUID | None = None,
    *,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    period_start: datetime | None = None,
    days: int = 30,
    with_next_charge: bool = True,
    cancel_at_period_end: bool = False,
    payment_token_id: uuid.UUID | None = None,
    dunning_attempt: int = 0,
    dunning_next_retry_at: datetime | None = None,
    grace_until: datetime | None = None,
    previous_plan_id: uuid.UUID | None = None,
) -> Subscription:
    start = period_start or now_utc()
    end = start + timedelta(days=days)
    return Subscription(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        plan_id=plan.id,
        status=status,
        current_period_start=start,
        current_period_end=end,
        next_charge_at=end if with_next_charge else None,
        cancel_at_period_end=cancel_at_period_end,
        payment_token_id=payment_token_id,
        dunning_attempt=dunning_attempt,
        dunning_next_retry_at=dunning_next_retry_at,
        grace_until=grace_until,
        previous_plan_id=previous_plan_id,
    )


def make_payment_txn(
    tenant_id: uuid.UUID,
    *,
    amount: str = "30.00",
    meta: dict | None = None,
    hidden_description: str | None = None,
    status: PaymentStatus = PaymentStatus.PENDING,
    transaction_id: str | None = None,
) -> PaymentTransaction:
    return PaymentTransaction(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        provider="tpay",
        transaction_id=transaction_id,
        hidden_description=hidden_description or str(uuid.uuid4()),
        amount=Decimal(amount),
        currency="PLN",
        status=status,
        meta=dict(meta or {}),
    )


def make_change_history(
    tenant_id: uuid.UUID,
    *,
    from_plan: PlanName,
    to_plan: PlanName,
    change_type: PlanChangeType = PlanChangeType.UPGRADE,
    status: PlanChangeStatus = PlanChangeStatus.PENDING,
    proration_details: dict | None = None,
) -> PlanChangeHistory:
    return PlanChangeHistory(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        from_plan=from_plan,
        to_plan=to_plan,
        change_type=change_type,
        requested_at=now_utc(),
        status=status,
        proration_details=dict(proration_details or {}),
    )


# --- Metody płatności (realne szyfrowanie per-tenant — roundtrip 1.54) ---


def saved_card_token(
    tenant_id: uuid.UUID,
    *,
    value: str = "tbe_card_1234",
    status: TpayTokenStatus = TpayTokenStatus.ACTIVE,
    is_default: bool = True,
) -> PaymentToken:
    return PaymentToken(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind=TokenKind.CARD_TOKEN,
        value_encrypted=encrypt_token_value(tenant_id, value),
        value_digest=token_digest(tenant_id, value),
        card_tail="0016",
        card_brand="mastercard",
        tpay_status=status,
        is_default=is_default,
    )


def saved_blik_alias(
    tenant_id: uuid.UUID,
    *,
    value: str = "tg-alias-payid-1",
    status: TpayTokenStatus = TpayTokenStatus.ACTIVE,
) -> PaymentToken:
    return PaymentToken(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind=TokenKind.BLIK_ALIAS_PAYID,
        value_encrypted=encrypt_token_value(tenant_id, value),
        value_digest=token_digest(tenant_id, value),
        tpay_status=status,
    )


# --- Provider i aplikacja ---


def make_scenario_provider() -> TpayProvider:
    """Provider tpay z testowymi ustawieniami sandbox i przypiętym certyfikatem.

    Metody HTTP (``create_checkout``/``charge_recurring``/…) nadpisują testy
    przez ``AsyncMock`` — JWS/md5 weryfikuje realny weryfikator.
    """
    return TpayProvider(make_test_billing_settings(), pinned_cert_pem=signing_cert_pem())


def install_app_overrides(
    app,
    *,
    user,
    db,
    provider: TpayProvider,
    role: str = "owner",
) -> uuid.UUID:
    """Nadpisanie zależności: użytkownik Owner + mock DB + provider (wzorzec 7.4)."""
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db, get_payment_provider

    tenant_id = getattr(user, "_tenant_id", None) or uuid.uuid4()
    user._tenant_id = tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = role
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_payment_provider] = lambda: provider
    return tenant_id


async def post_tpay_notification(client, body: bytes, *, json_content: bool = False):
    """Webhook tpay z podpisanym JWS body (form albo JSON)."""
    content_type = "application/json" if json_content else "application/x-www-form-urlencoded"
    return await client.post(
        "/api/v1/billing/webhooks/tpay",
        content=body,
        headers={"Content-Type": content_type, "X-JWS-Signature": sign_jws(body)},
    )


# --- Konteksty: maile (sandbox je blokuje) i pipeline faktur (7.6) ---


@contextmanager
def billing_emails_mocked() -> Iterator[dict[str, MagicMock]]:
    """Wszystkie maile billingowe na mockach (§4.4 — w sandboxie zablokowane).

    Patchuje miejsce użycia: importy top-level (subscription_service,
    webhook_processor) oraz moduł email_service (importy leniwe w funkcjach).
    """
    with (
        patch("app.services.email.email_service.send_payment_confirmation_email") as confirmation,
        patch("app.services.email.email_service.send_plan_changed_email") as plan_changed,
        patch("app.services.billing.subscription_service.send_payment_failed_email") as payment_failed,
        patch("app.services.billing.subscription_service.send_subscription_downgraded_email") as downgraded,
        patch("app.services.billing.webhook_processor.send_payment_method_expired_email") as method_expired,
    ):
        yield {
            "confirmation": confirmation,
            "plan_changed": plan_changed,
            "payment_failed": payment_failed,
            "downgraded": downgraded,
            "method_expired": method_expired,
        }


@contextmanager
def invoice_pipeline_mocked() -> Iterator[tuple[MagicMock, MagicMock]]:
    """Faktura VAT (7.6) na mockach: ``InvoiceService`` + task Celery PDF."""
    with (
        patch("app.services.billing.webhook_processor.InvoiceService") as invoice_service,
        patch("app.workers.tasks.generate_invoice_pdf.generate_invoice_pdf") as pdf_task,
    ):
        invoice_service.return_value.generate_invoice = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
        yield invoice_service, pdf_task


def owner_user(email: str = "owner@testcompany.pl", name: str = "Owner"):
    """Owner tenanta (rola ustawiana w ``install_app_overrides``)."""
    return make_user(email=email, name=name)


# --- Kompozytory sekwencji DB dla webhooka transakcyjnego (7.4 AC5) ---


def paid_webhook_results(txn: PaymentTransaction, plan: SubscriptionPlan, sub: Subscription | None) -> list:
    """Wyniki ``execute`` webhooka ``tr_status=true`` (pełna kwota) — do
    łączenia z dalszą sekwencją (np. zapis karty przy save=1)."""
    return [
        MagicMock(),  # SET LOCAL app.current_tenant (RLS, przepływ systemowy)
        scalar(None),  # dedup webhook_events
        scalar(txn),  # korelacja hidden_description == tr_crc
        scalar(plan),  # activate_paid_plan: select planu
        scalar(sub),  # activate_paid_plan: subskrypcja (None → nowa)
        MagicMock(),  # UPDATE tenants.plan (legacy gating modułów)
    ]


def paid_webhook_db(txn: PaymentTransaction, plan: SubscriptionPlan, sub: Subscription | None):
    """Sekwencja ``execute`` dla webhooka ``tr_status=true`` (pełna kwota):
    SET LOCAL RLS → dedup ``event_uid`` → korelacja ``tr_crc`` → aktywacja
    (plan + subskrypcja + UPDATE tenants.plan)."""
    return make_mock_db(*paid_webhook_results(txn, plan, sub))


def declined_webhook_db(txn: PaymentTransaction):
    """Sekwencja ``execute`` dla webhooka porażki (``tr_status=false``,
    zakup — bez źródła recurring): SET LOCAL → dedup → korelacja."""
    return make_mock_db(
        MagicMock(),  # SET LOCAL RLS
        scalar(None),  # dedup
        scalar(txn),  # korelacja tr_crc
    )
