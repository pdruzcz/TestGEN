"""SubscriptionService — plany, subskrypcje, limity (Story 7.1) + aktywacja po
zapłacie (7.4) + metody płatności i dunning (7.2).

Jedno źródło prawdy limitów: ``subscription_plans.features`` (JSONB, DB).
Nowy tenant dostaje automatycznie subskrypcję Freemium (AC2) — wywołanie
z procesu rejestracji (auth_service.register). Aktywacja planu zakupionego
(webhook paid / reconciliation) — Story 7.4 AC5.

Metody płatności (7.2): wartości tokenów AES-256-GCM per-tenant (wzorzec
1.54 — ``app.core.encryption``); digest SHA-256 umożliwia wyszukiwanie
(GCM losowy nonce → blob nieporównywalny).
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_billing import get_billing_settings
from app.core.encryption import decrypt_bytes_for_tenant, encrypt_bytes_for_tenant
from app.core.exceptions import ConflictError, NotFoundError
from app.models.invoice import Invoice
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
from app.models.tenant import Tenant
from app.models.usage import CounterType, UsageCounter
from app.services.email.email_service import (
    send_payment_failed_email,
    send_subscription_downgraded_email,
)

if TYPE_CHECKING:  # TC001 — typ tylko do adnotacji (cache trzyma instancje w runtime)
    from app.services.billing.providers.base import PaymentProvider, ProviderTokenStatus

# Plan płatny (checkout 7.4) — Freemium nie podlega zakupowi (AC1).
PAID_PLANS: tuple[PlanName, ...] = (PlanName.BASIC, PlanName.PREMIUM)

# Dunning (AC6): 3 ponowienia po nieudanym obciążeniu — D+1, D+3, D+5
# (offsety w dniach od porażki); po 3. porażce downgrade do Freemium
# z 7-dniowym grace na planie, który był (CR#2).
DUNNING_RETRY_OFFSETS_DAYS: tuple[int, ...] = (1, 3, 5)
DUNNING_GRACE_DAYS: int = 7

# Story 7.7 (Task 1.1) — krótkoterminowy cache stanu tokenów z GET /tokens/{value}:
# ogranicza wywołania tpay przy odświeżaniu listy metod płatności w portalu.
TOKEN_STATUS_CACHE_TTL_SECONDS: float = 300.0
_token_status_cache: dict[uuid.UUID, tuple[float, "ProviderTokenStatus"]] = {}

logger = logging.getLogger(__name__)

# Hierarchia planów (CR#2): Freemium (0) < Basic (30) < Premium (50).
PLAN_HIERARCHY: dict[PlanName, int] = {
    PlanName.FREEMIUM: 0,
    PlanName.BASIC: 1,
    PlanName.PREMIUM: 2,
}

# Mapowanie CounterType → klucz w features planu
_COUNTER_FEATURE_KEYS: dict[CounterType, str] = {
    CounterType.ANALYSES: "analyses",
    CounterType.TEST_CASES: "test_cases",
    CounterType.STORAGE_BYTES: "storage_bytes",
    CounterType.FILES_PER_ANALYSIS: "files_per_analysis",
}


def _month_window(now: datetime) -> tuple[datetime, datetime]:
    """Okres miesięczny [start, end) od pierwszego dnia bieżącego miesiąca."""
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return start, end


# --- Story 7.5: lokalny proration (D2 — liczymy sami, bez API dostawcy) ---


def plan_monthly_price(plan: PlanName) -> Decimal:
    """Cena miesięczna planu z konfiguracji (env §3.2a) — Freemium = 0."""
    billing = get_billing_settings()
    if plan == PlanName.BASIC:
        return billing.billing_basic_monthly_price
    if plan == PlanName.PREMIUM:
        return billing.billing_premium_monthly_price
    return Decimal("0.00")


def calculate_proration(
    *,
    current_plan: PlanName,
    new_plan: PlanName,
    period_start: datetime,
    period_end: datetime,
    now: datetime,
    current_price: Decimal,
    new_price: Decimal,
) -> dict:
    """Czysta funkcja proration (AC1/AC5) — Decimal, ROUND_HALF_UP, 2 miejsca.

    Płatny→płatny: ``((nowa cena / dni okresu) * pozostałe dni)
    - ((stara cena / dni okresu) * pozostałe dni)``; wynik ujemny → 0,00
    (AC1: ostatni dzień okresu = upgrade bez obciążenia).
    Z Freemium: pełna cena nowego planu (brak komponentu prorated).
    Downgrade: 0,00 (rozliczenie na koniec okresu, bez zwrotu — AC2).

    Zwraca słownik audytowy do ``proration_details`` (AC4).
    """
    period_days = max((period_end - period_start).days, 1)
    remaining_days = max((period_end - now).days, 0)

    if PLAN_HIERARCHY[new_plan] <= PLAN_HIERARCHY[current_plan]:
        amount = Decimal("0.00")  # downgrade — bez komponentu prorated (AC2)
    elif current_plan == PlanName.FREEMIUM:
        amount = new_price  # pełna cena nowego planu (AC1)
    else:
        raw = (new_price / period_days) * remaining_days - (current_price / period_days) * remaining_days
        amount = max(raw, Decimal("0"))

    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "amount": str(amount),
        "period_days": period_days,
        "remaining_days": remaining_days,
        "current_plan": current_plan.value,
        "new_plan": new_plan.value,
        "current_price": str(current_price.quantize(Decimal("0.01"))),
        "new_price": str(new_price.quantize(Decimal("0.01"))),
    }


@dataclass(frozen=True)
class PlanChangeResult:
    """Wynik ``change_plan`` — dla API (Story 7.5)."""

    change: PlanChangeHistory
    change_type: PlanChangeType
    amount: Decimal
    payment_required: bool
    payment_url: str | None = None
    order_id: str | None = None


@dataclass(frozen=True)
class SubscriptionDetail:
    """Widok detailu subskrypcji dla portalu billingowego (Story 7.7, AC3)."""

    subscription: Subscription
    plan: SubscriptionPlan | None = None
    payment_method: PaymentToken | None = None
    pending_change: PlanChangeHistory | None = None


@dataclass(frozen=True)
class TransactionListItem:
    """Transakcja z derywowaną metodą płatności i powiązaną fakturą (AC2)."""

    transaction: PaymentTransaction
    method: str | None = None  # card | blik | bank_transfer | None (nieznana)
    invoice: Invoice | None = None


# --- Szyfrowanie wartości tokenów (AC1 — AES-256-GCM per-tenant, wzorzec 1.54) ---


def encrypt_token_value(tenant_id: uuid.UUID, value: str) -> bytes:
    """Token karty / alias BLIK → blob AES-256-GCM pod kluczem tenanta."""
    return encrypt_bytes_for_tenant(value.encode("utf-8"), tenant_id)


def decrypt_token_value(tenant_id: uuid.UUID, blob: bytes) -> str:
    """Odszyfrowanie blobu tokena w kontekście tenanta (InvalidTag = obcy klucz)."""
    return decrypt_bytes_for_tenant(blob, tenant_id).decode("utf-8")


def token_digest(tenant_id: uuid.UUID, value: str) -> str:
    """Deterministyczny digest do wyszukiwania/idempotencji (nonce GCM losowy).

    SHA-256 z prefiksem tenant_id — bez ujawniania wartości (token ma wysoką
    entropię, digest nieodwracalny w praktyce); scoping per-tenant.
    """
    return hashlib.sha256(f"{tenant_id}:{value}".encode()).hexdigest()


def _map_tpay_status(value: str) -> TpayTokenStatus | None:
    """Status z GET /tokens/{value} (ACTIVE|SUSPENDED|DELETED) → enum; None = nieznany."""
    try:
        return TpayTokenStatus(value.strip().lower())
    except ValueError:
        logger.warning("Nieznany status tokena u tpay: %r — pozostawiam lokalny", value)
        return None



async def _emit_subscription_changed(
    tenant_id, old_plan: str | None, new_plan: str, effective_date
) -> None:
    """Webhook ``subscription.changed`` (Story 8.7, AC2).

    Wołane po utrwaleniu zmiany planu — zarówno przy upgrade (po płatności),
    jak i przy egzekucji zaplanowanego downgradu. Emiter jest cichy: awaria
    powiadomienia nie może cofnąć rozliczonej zmiany planu.
    """
    try:
        from app.services.integrations.event_emitter import emit_event_standalone

        await emit_event_standalone(
            "subscription.changed",
            tenant_id,
            {
                "old_plan": old_plan,
                "new_plan": new_plan,
                "effective_date": effective_date.isoformat() if effective_date else None,
            },
        )
    except Exception:
        logger.warning("Nie udało się wyemitować subscription.changed", exc_info=True)


class SubscriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_plans(self) -> list[SubscriptionPlan]:
        """Aktywne plany w kolejności sort_order (Freemium → Basic → Premium)."""
        result = await self._db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.sort_order)
        )
        return list(result.scalars().all())

    async def get_current_subscription(self, tenant_id: uuid.UUID) -> Subscription | None:
        result = await self._db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id))
        return result.scalar_one_or_none()

    async def get_plan_limits(self, plan_name: PlanName) -> dict:
        """Macierz limitów planu wprost z DB (features JSONB) — jedno źródło prawdy."""
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name))
        plan = result.scalar_one_or_none()
        return dict(plan.features) if plan else {}

    async def create_freemium_subscription(self, tenant_id: uuid.UUID) -> Subscription:
        """AC2 — subskrypcja Freemium przy rejestracji (idempotentna)."""
        existing = await self.get_current_subscription(tenant_id)
        if existing is not None:
            return existing

        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == PlanName.FREEMIUM))
        plan = result.scalar_one_or_none()
        if plan is None:
            raise LookupError("Plan freemium nie istnieje — uruchom seed planów (seed_subscription_plans)")

        start = datetime.now(UTC)
        subscription = Subscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=start,
            current_period_end=start + timedelta(days=30),
            cancel_at_period_end=False,
        )
        self._db.add(subscription)
        await self._db.flush()
        return subscription

    async def get_active_paid_plan_name(self, tenant_id: uuid.UUID) -> PlanName | None:
        """Nazwa aktywnego planu płatnego tenanta (AC1: 409 przy checkoucie).

        Freemium / brak subskrypcji / status inny niż active → None
        (można kupować). Basic→Premium idzie przez /subscription/change (7.5).
        """
        subscription = await self.get_current_subscription(tenant_id)
        if subscription is None or subscription.status != SubscriptionStatus.ACTIVE:
            return None
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id))
        plan = result.scalar_one_or_none()
        if plan is None or plan.name not in PAID_PLANS:
            return None
        return plan.name

    async def activate_paid_plan(self, tenant_id: uuid.UUID, plan_name: PlanName) -> Subscription:
        """Aktywacja zakupionego planu po `paid` (AC5) lub reconciliation (AC7).

        Okres: [now, now + 30 dni], ``next_charge_at`` = koniec okresu (jedyny
        cykl — miesięczny). Spójna aktualizacja ``tenants.plan`` (legacy
        kolumna gatingu modułów — enum PlanType, ta sama wartość).
        Liczniki użycia resetują się naturalnie na nowy okres (okny są
        per period_start/period_end; brak wiersza = 0 użycia).
        """
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name))
        plan = result.scalar_one_or_none()
        if plan is None:
            raise LookupError(f"Plan {plan_name} nie istnieje — uruchom seed planów (seed_subscription_plans)")

        now = datetime.now(UTC)
        period_end = now + timedelta(days=30)

        subscription = await self.get_current_subscription(tenant_id)
        if subscription is None:
            subscription = Subscription(tenant_id=tenant_id, plan_id=plan.id)
            self._db.add(subscription)
        subscription.plan_id = plan.id
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.current_period_start = now
        subscription.current_period_end = period_end
        subscription.next_charge_at = period_end  # jedyny cykl: +1 miesiąc
        subscription.cancel_at_period_end = False

        # Legacy kolumna tenants.plan (gating modułów) — spójność z subskrypcją.
        await self._db.execute(update(Tenant).where(Tenant.id == tenant_id).values(plan=plan_name))
        await self._db.flush()
        return subscription

    async def check_quota(self, tenant_id: uuid.UUID, counter_type: CounterType) -> bool:
        """Czy tenant mieści się w limicie ``counter_type`` na aktualny okres.

        Plan efektywny (7.2 AC6): w grace po downgrade → limity planu, który
        był (``previous_plan_id``); po wygaśnięciu grace — Freemium.
        """
        subscription = await self.get_current_subscription(tenant_id)
        if subscription is None:
            return True  # brak subskrypcji → nie blokujemy (kwestia 7.2 dunning)

        plan = await self.get_effective_plan(subscription)
        if plan is None:
            return True

        feature_key = _COUNTER_FEATURE_KEYS[counter_type]
        limit = plan.features.get(feature_key)
        if limit is None:  # unlimited
            return True

        period_start, period_end = _month_window(datetime.now(UTC))
        counter_result = await self._db.execute(
            select(UsageCounter).where(
                UsageCounter.tenant_id == tenant_id,
                UsageCounter.counter_type == counter_type,
                UsageCounter.period_start == period_start,
                UsageCounter.period_end == period_end,
            )
        )
        counter = counter_result.scalar_one_or_none()
        used = counter.value if counter is not None else 0
        return used < limit

    async def get_effective_plan(self, subscription: Subscription) -> SubscriptionPlan | None:
        """Plan dla limitów: grace (past_due + ``grace_until`` > now) → plan
        przed downgrade'em (``previous_plan_id``); inaczej plan bieżący."""
        now = datetime.now(UTC)
        if (
            subscription.status == SubscriptionStatus.PAST_DUE
            and subscription.grace_until is not None
            and subscription.grace_until > now
            and subscription.previous_plan_id is not None
        ):
            result = await self._db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.previous_plan_id)
            )
            plan = result.scalar_one_or_none()
            if plan is not None:
                return plan
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id))
        return result.scalar_one_or_none()

    # --- Story 7.2: dunning (AC6) ---

    async def register_failed_charge(
        self,
        subscription: Subscription,
        *,
        owner_email: str | None = None,
    ) -> None:
        """Zarejestrowanie nieudanego obciążenia cyklicznego (AC6).

        Eskalacja: porażka początkowa → próby D+1/D+3/D+5 (3 ponowienia);
        każda kolejna porażka zwiększa ``dunning_attempt``. Po 3. nieudanym
        PONOWIENIU (4. porażka łącznie): ``status = past_due`` + downgrade
        ZAWSZE do Freemium (nie „o poziom niżej" — CR#2) z 7-dniowym grace
        na planie, który był. Każda porażka → email do Ownera.
        """
        subscription.dunning_attempt = (subscription.dunning_attempt or 0) + 1
        attempt = subscription.dunning_attempt

        if attempt > len(DUNNING_RETRY_OFFSETS_DAYS):
            await self._apply_dunning_downgrade(subscription, owner_email=owner_email)
            return

        offset_days = DUNNING_RETRY_OFFSETS_DAYS[attempt - 1]
        subscription.dunning_next_retry_at = datetime.now(UTC) + timedelta(days=offset_days)
        await self._db.flush()

        if owner_email:
            self._notify_payment_failed(owner_email, subscription, attempt=attempt, retry_in_days=offset_days)

    async def _apply_dunning_downgrade(self, subscription: Subscription, *, owner_email: str | None) -> None:
        """Downgrade do Freemium + grace (CR#2). Legacy ``tenants.plan`` zostaje
        na planie płatnym do końca grace (gating modułów = limity grace)."""
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == PlanName.FREEMIUM))
        freemium = result.scalar_one_or_none()
        if freemium is None:
            raise LookupError("Plan freemium nie istnieje — uruchom seed planów (seed_subscription_plans)")

        previous_plan_id = subscription.plan_id
        subscription.previous_plan_id = previous_plan_id
        subscription.plan_id = freemium.id
        subscription.status = SubscriptionStatus.PAST_DUE
        subscription.grace_until = datetime.now(UTC) + timedelta(days=DUNNING_GRACE_DAYS)
        subscription.dunning_next_retry_at = None
        await self._db.flush()

        logger.warning(
            "DOWNGRADE do Freemium (dunning): tenant=%s poprzedni plan=%s grace_do=%s",
            subscription.tenant_id,
            previous_plan_id,
            subscription.grace_until,
        )
        if owner_email:
            self._notify_downgrade(owner_email, subscription)

    async def renew_subscription(self, tenant_id: uuid.UUID, plan_name: PlanName) -> Subscription:
        """AC5/Task 5.4 — odnowienie po ``paid`` odnowienia (webhook, source=recurring).

        Przedłużenie okresu od ``current_period_end`` (ciągłość rozliczeń),
        ``next_charge_at`` = nowy koniec (jedyny cykl: +1 miesiąc), czyszczenie
        stanu dunningu. Spóźniona wpłata w grace (``past_due``) przywraca plan
        sprzed downgrade'u (``previous_plan_id``).
        """
        subscription = await self.get_current_subscription(tenant_id)
        if subscription is None:
            raise LookupError(f"Brak subskrypcji tenanta {tenant_id} przy odnowieniu")

        now = datetime.now(UTC)
        if subscription.status == SubscriptionStatus.PAST_DUE and subscription.previous_plan_id is not None:
            # Powrót na plan sprzed downgrade'u — nowy okres od teraz.
            restore_id = subscription.previous_plan_id
            subscription.previous_plan_id = None
            subscription.grace_until = None
            subscription.plan_id = restore_id
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=30)
        else:
            # Ciągłość rozliczeń: nowy okres zaczyna się tam, gdzie skończył stary.
            subscription.current_period_start = subscription.current_period_end
            subscription.current_period_end = subscription.current_period_start + timedelta(days=30)

        subscription.status = SubscriptionStatus.ACTIVE
        subscription.next_charge_at = subscription.current_period_end
        subscription.dunning_attempt = 0
        subscription.dunning_next_retry_at = None

        # Legacy kolumna tenants.plan (gating modułów) — spójność z subskrypcją.
        await self._db.execute(update(Tenant).where(Tenant.id == tenant_id).values(plan=plan_name))
        await self._db.flush()
        return subscription

    async def enforce_grace_expiry(self, subscription: Subscription) -> None:
        """Po wygaśnięciu grace (7.2 AC6): egzekwowanie Freemium — legacy
        ``tenants.plan`` (gating modułów) przechodzi na freemium. Limitami
        (``check_quota``) od downgrade'u rządzi już ``plan_id`` + grace."""
        now = datetime.now(UTC)
        if (
            subscription.status != SubscriptionStatus.PAST_DUE
            or subscription.grace_until is None
            or subscription.grace_until > now
        ):
            return
        subscription.grace_until = None
        await self._db.execute(update(Tenant).where(Tenant.id == subscription.tenant_id).values(plan=PlanName.FREEMIUM))
        await self._db.flush()

    def _notify_payment_failed(
        self, owner_email: str, subscription: Subscription, *, attempt: int, retry_in_days: int
    ) -> None:
        """Email „płatność nie powiodła się" (AC6) — best-effort."""
        try:
            send_payment_failed_email(
                email=owner_email,
                attempt=attempt,
                attempts_total=len(DUNNING_RETRY_OFFSETS_DAYS),
                retry_in_days=retry_in_days,
            )
        except Exception:
            logger.warning("Email o nieudanej płatności nie wysłany — dunning kontynuuje", exc_info=True)

    def _notify_downgrade(self, owner_email: str, subscription: Subscription) -> None:
        """Email o downgrade + grace (AC6) — best-effort."""
        try:
            send_subscription_downgraded_email(
                email=owner_email,
                grace_days=DUNNING_GRACE_DAYS,
            )
        except Exception:
            logger.warning("Email o downgrade nie wysłany — dunning kontynuuje", exc_info=True)

    # --- Story 7.2: metody płatności (PaymentToken — AC1/AC2/AC3) ---

    async def save_card_token_from_webhook(
        self,
        tenant_id: uuid.UUID,
        *,
        token_value: str,
        card_tail: str | None,
        card_brand: str | None,
    ) -> PaymentToken:
        """AC1 — zapis tokena karty z webhooka transakcyjnego (save=1).

        Idempotentny po ``value_digest`` (ponowienia notyfikacji nie dublują).
        Pierwsza metoda tenanta staje się domyślna i wiąże się z subskrypcją
        jako aktywna metoda odnowień.
        """
        digest = token_digest(tenant_id, token_value)
        existing = await self._find_token_by_digest(tenant_id, digest)
        if existing is not None:
            return existing

        token = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=TokenKind.CARD_TOKEN,
            value_encrypted=encrypt_token_value(tenant_id, token_value),
            value_digest=digest,
            card_tail=card_tail,
            card_brand=card_brand,
            tpay_status=TpayTokenStatus.ACTIVE,
        )
        self._db.add(token)
        await self._db.flush()
        await self._link_default_method(tenant_id, token)
        return token

    async def save_card_token_from_notification(
        self,
        tenant_id: uuid.UUID,
        *,
        token_value: str,
        registration_id: str | None = None,
        card_tail: str | None = None,
        card_brand: str | None = None,
    ) -> PaymentToken:
        """AC2/Task 3.3 — zapis z notyfikacji JSON ``data.token`` (POST /tokens).

        ``registration_id`` (``cliAuth``) potwierdza rekord PENDING utworzony
        przez POST /payment-methods; bez niego (np. brak cliAuth u tpay)
        deduplikujemy po ``value_digest`` i ewentualnie tworzymy nowy rekord.
        Delegacja z dispatchera notyfikacji — Story 7.3.
        """
        token: PaymentToken | None = None
        if registration_id:
            result = await self._db.execute(select(PaymentToken).where(PaymentToken.registration_id == registration_id))
            token = result.scalar_one_or_none()

        if token is None:
            digest = token_digest(tenant_id, token_value)
            token = await self._find_token_by_digest(tenant_id, digest)
        if token is None:
            token = PaymentToken(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                kind=TokenKind.CARD_TOKEN,
            )
            self._db.add(token)

        token.kind = TokenKind.CARD_TOKEN
        token.value_encrypted = encrypt_token_value(tenant_id, token_value)
        token.value_digest = token_digest(tenant_id, token_value)
        if card_tail:
            token.card_tail = card_tail
        if card_brand:
            token.card_brand = card_brand
        token.tpay_status = TpayTokenStatus.ACTIVE
        await self._db.flush()
        return token

    async def save_blik_alias_from_notification(
        self,
        tenant_id: uuid.UUID,
        *,
        alias_value: str,
        kind: TokenKind = TokenKind.BLIK_ALIAS_PAYID,
        expires_at: datetime | None = None,
    ) -> PaymentToken:
        """AC4 — notyfikacja ``ALIAS_REGISTER`` → PaymentToken (realizacja
        dispatchera w 7.3; korelacja tenanta po transakcji rejestracji).

        ``kind``: domyślnie PAYID; ``blik_alias_uid`` jeśli dotyczy.
        Idempotentny po ``value_digest``; statusy zmieniają notyfikacje
        ``ALIAS_UPDATE``/``ALIAS_UNREGISTER``/``ALIAS_EXPIRED`` (7.3).
        """
        digest = token_digest(tenant_id, alias_value)
        existing = await self._find_token_by_digest(tenant_id, digest)
        if existing is not None:
            return existing

        token = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=kind,
            value_encrypted=encrypt_token_value(tenant_id, alias_value),
            value_digest=digest,
            tpay_status=TpayTokenStatus.ACTIVE,
            expires_at=expires_at,
        )
        self._db.add(token)
        await self._db.flush()
        await self._link_default_method(tenant_id, token)
        return token

    async def find_blik_alias_token(self, tenant_id: uuid.UUID, alias_value: str) -> PaymentToken | None:
        """7.3 AC3 — alias BLIK tenanta po wartości (digest, bez odszyfrowywania)."""
        return await self._find_token_by_digest(tenant_id, token_digest(tenant_id, alias_value))

    async def update_blik_alias_status(
        self,
        tenant_id: uuid.UUID,
        alias_value: str,
        *,
        tpay_status: TpayTokenStatus,
        expires_at: datetime | None = None,
    ) -> PaymentToken | None:
        """7.3 AC3 — ``ALIAS_UPDATE``/``ALIAS_UNREGISTER``/``ALIAS_EXPIRED``:
        aktualizacja ``tpay_status`` (ACTIVE|SUSPENDED|DELETED) i danych aliasu.
        Brak tokenu → None (warning w dispatcherze, nie 500). Przy DELETED
        odwiązuje metodę z subskrypcji (promocja kolejnej aktywnej — mirror
        ``delete_payment_method``, ale bez 409: notyfikacja nigdy nie failuje)."""
        token = await self.find_blik_alias_token(tenant_id, alias_value)
        if token is None:
            return None

        token.tpay_status = tpay_status
        if expires_at is not None:
            token.expires_at = expires_at
        if tpay_status == TpayTokenStatus.DELETED:
            token.is_default = False
            subscription = await self.get_current_subscription(tenant_id)
            if subscription is not None and subscription.payment_token_id == token.id:
                others = await self._other_active_tokens(tenant_id, token.id)
                subscription.payment_token_id = others[0].id if others else None
                if others:
                    others[0].is_default = True
        await self._db.flush()
        return token

    async def create_pending_registration(self, tenant_id: uuid.UUID, *, registration_id: str) -> PaymentToken:
        """AC2 — rekord PENDING przed przekierowaniem na rejestrację /tokens.

        Potwierdzenie (pending→confirmed) następuje notyfikacją ``data.token``
        (``save_card_token_from_notification``); FE pollinguje listę metod.
        Rekord od razu wiąże się z subskrypcją jako aktywna metoda — scheduler
        obciąża wyłącznie tokeny w stanie ACTIVE, więc PENDING nie zostanie
        użyty przed potwierdzeniem.
        """
        token = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=TokenKind.CARD_TOKEN,
            tpay_status=TpayTokenStatus.PENDING,
            registration_id=registration_id,
        )
        self._db.add(token)
        await self._db.flush()
        await self._link_default_method(tenant_id, token)
        return token

    async def list_payment_methods(self, tenant_id: uuid.UUID) -> list[PaymentToken]:
        """AC3 — metody tenanta: domyślna pierwsza, potem najnowsze."""
        result = await self._db.execute(
            select(PaymentToken)
            .where(PaymentToken.tenant_id == tenant_id)
            .order_by(PaymentToken.is_default.desc(), PaymentToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def refresh_payment_method_statuses(
        self,
        tenant_id: uuid.UUID,
        *,
        provider: "PaymentProvider",
    ) -> tuple[list[PaymentToken], bool]:
        """Story 7.7 (AC1/Task 1.1) — wzbogacenie listy metod o stan z tpay.

        Karty (``card_token``) odświeżane przez ``GET /tokens/{value}`` z krót-
        koterminowym cache'em (TTL); dryf statusu/wizerunku (brand, ogon,
        ważność) zapisywany lokalnie (zwraca ``changed`` → route commituje).
        Aliasy BLIK (osobny endpoint u tpay) i rejestracje pending (brak
        wartości) są pomijane. Błąd dostawcy → stan lokalny (graceful degrade,
        bez 502) — lista metod nie może zależeć od dostępności tpay.
        """
        methods = await self.list_payment_methods(tenant_id)
        changed = False
        now = time.monotonic()
        for token in methods:
            if (
                token.kind != TokenKind.CARD_TOKEN
                or not token.value_encrypted
                or token.tpay_status in (TpayTokenStatus.DELETED, TpayTokenStatus.PENDING)
            ):
                continue
            cached = _token_status_cache.get(token.id)
            if cached is not None and now - cached[0] < TOKEN_STATUS_CACHE_TTL_SECONDS:
                continue
            try:
                remote = await provider.get_token_status(await self.get_token_value(token))
            except Exception:
                logger.warning(
                    "tpay get_token_status nie powiódł się (token %s, tenant %s) — stan lokalny",
                    token.id,
                    tenant_id,
                )
                continue
            _token_status_cache[token.id] = (now, remote)

            remote_status = _map_tpay_status(remote.status)
            if remote_status is not None and remote_status != token.tpay_status:
                token.tpay_status = remote_status
                changed = True
            if remote.card_brand and remote.card_brand != token.card_brand:
                token.card_brand = remote.card_brand
                changed = True
            if remote.card_tail and remote.card_tail != token.card_tail:
                token.card_tail = remote.card_tail
                changed = True
            if remote.expires_at is not None and (
                token.expires_at is None or token.expires_at.date() != remote.expires_at
            ):
                token.expires_at = datetime(
                    remote.expires_at.year, remote.expires_at.month, remote.expires_at.day, tzinfo=UTC
                )
                changed = True
        if changed:
            await self._db.flush()
        return methods, changed

    async def delete_payment_method(
        self,
        tenant_id: uuid.UUID,
        token_id: uuid.UUID,
        *,
        token: PaymentToken | None = None,
    ) -> PaymentToken:
        """AC3 — soft delete (``tpay_status = DELETED``); zdalne DELETE u tpay
        orchestruje route (provider, który przekazuje tu prefetched token).
        409 na usunięcie JEDYNEJ aktywnej metody przy aktywnej subskrypcji
        cyklicznej (najpierw dodaj inną metodę)."""
        token = token or await self._get_token(tenant_id, token_id)
        if token.tpay_status == TpayTokenStatus.DELETED:
            return token  # idempotentny soft delete

        others = await self._other_active_tokens(tenant_id, token_id)
        subscription = await self.get_current_subscription(tenant_id)
        if (
            not others
            and subscription is not None
            and subscription.status == SubscriptionStatus.ACTIVE
            and subscription.next_charge_at is not None
            and not subscription.cancel_at_period_end
        ):
            raise ConflictError(
                "To jedyna aktywna metoda płatności subskrypcji cyklicznej — najpierw dodaj inną metodę płatności"
            )

        token.tpay_status = TpayTokenStatus.DELETED
        token.is_default = False
        # Odwiązanie z subskrypcji + promocja kolejnej metody na domyślną.
        if subscription is not None and subscription.payment_token_id == token.id:
            subscription.payment_token_id = others[0].id if others else None
            if others:
                others[0].is_default = True
        await self._db.flush()
        return token

    async def get_payment_method(self, tenant_id: uuid.UUID, token_id: uuid.UUID) -> PaymentToken:
        """Pojedyncza metoda tenanta (RLS per-tenant; 404 gdy obcy identyfikator)."""
        return await self._get_token(tenant_id, token_id)

    async def get_token_value(self, token: PaymentToken) -> str:
        """Odszyfrowanie wartości tokena w kontekście właściciela (scheduler)."""
        return decrypt_token_value(token.tenant_id, token.value_encrypted)

    async def _find_token_by_digest(self, tenant_id: uuid.UUID, digest: str) -> PaymentToken | None:
        result = await self._db.execute(
            select(PaymentToken).where(
                PaymentToken.tenant_id == tenant_id,
                PaymentToken.value_digest == digest,
            )
        )
        return result.scalar_one_or_none()

    async def _get_token(self, tenant_id: uuid.UUID, token_id: uuid.UUID) -> PaymentToken:
        result = await self._db.execute(
            select(PaymentToken).where(PaymentToken.id == token_id, PaymentToken.tenant_id == tenant_id)
        )
        token = result.scalar_one_or_none()
        if token is None:
            raise NotFoundError("Payment method not found")
        return token

    async def _other_active_tokens(self, tenant_id: uuid.UUID, token_id: uuid.UUID) -> list[PaymentToken]:
        result = await self._db.execute(
            select(PaymentToken)
            .where(
                PaymentToken.tenant_id == tenant_id,
                PaymentToken.id != token_id,
                PaymentToken.tpay_status == TpayTokenStatus.ACTIVE,
            )
            .order_by(PaymentToken.created_at.desc())
        )
        return list(result.scalars().all())

    # --- Story 7.5: upgrade/downgrade planu z lokalnym proration (AC1-AC6) ---

    async def preview_proration(self, tenant_id: uuid.UUID, new_plan: PlanName) -> dict:
        """AC5 — lokalny podgląd proration, bez wywołania API tpay.

        Te same wejścia co przy obciążeniu (``change_plan``) — test spójności
        preview↔charge gwarantuje równość kwot.
        """
        subscription = await self.get_current_subscription(tenant_id)
        if subscription is None:
            raise NotFoundError("Subscription not found")
        current_plan = await self._plan_of(subscription)
        if current_plan.name == new_plan:
            raise ValueError("Nowy plan jest identyczny z aktualnym")

        change_type = (
            PlanChangeType.UPGRADE
            if PLAN_HIERARCHY[new_plan] > PLAN_HIERARCHY[current_plan.name]
            else PlanChangeType.DOWNGRADE
        )
        details = calculate_proration(
            current_plan=current_plan.name,
            new_plan=new_plan,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            now=datetime.now(UTC),
            current_price=plan_monthly_price(current_plan.name),
            new_price=plan_monthly_price(new_plan),
        )
        details["change_type"] = change_type.value
        details["full_price"] = str(plan_monthly_price(new_plan))
        details["currency"] = get_billing_settings().billing_currency
        details["next_charge_at"] = (
            subscription.current_period_end.isoformat() if subscription.current_period_end else None
        )
        return details

    async def change_plan(
        self,
        tenant_id: uuid.UUID,
        new_plan: PlanName,
        user_id: uuid.UUID | None,
        *,
        provider,
        owner_email: str,
        owner_name: str | None = None,
    ) -> PlanChangeResult:
        """AC1/AC2 — dispatch upgrade/downgrade wg hierarchii Freemium < Basic < Premium.

        Upgrade: obciążenie prorated (zapisana metoda z 7.2 albo checkout 7.4
        z kwotą custom), zmiana planu dopiero po webhooku ``paid`` (korelacja
        ``hidden_description``); kwota ≤ 0,00 → zmiana od razu bez obciążenia.
        Downgrade: czysto lokalnie (§3.5 — NIE wołamy API tpay):
        ``cancel_at_period_end = true`` + stop ``next_charge_at``.
        """
        subscription = await self._get_subscription_locked(tenant_id)
        if subscription is None:
            raise NotFoundError("Subscription not found")
        current_plan = await self._plan_of(subscription)
        if current_plan.name == new_plan:
            raise ValueError("Nowy plan jest identyczny z aktualnym")

        is_upgrade = PLAN_HIERARCHY[new_plan] > PLAN_HIERARCHY[current_plan.name]
        if not is_upgrade and subscription.status == SubscriptionStatus.PAST_DUE:
            # Task 3.2: downgrade podczas grace dunningu → 409.
            raise ConflictError("Subskrypcja w trakcie windykacji (dunning) — najpierw wyjaśnij stan płatności")

        now = datetime.now(UTC)
        # Edge 6.5: nowa zmiana nadpisuje oczekującą (cancel + przywrócenie stanu).
        pending = await self.get_pending_change(tenant_id)
        if pending is not None:
            self._revert_pending(pending, subscription)

        if is_upgrade:
            return await self._start_upgrade(
                subscription,
                current_plan,
                new_plan,
                user_id,
                now=now,
                provider=provider,
                owner_email=owner_email,
                owner_name=owner_name,
            )
        return await self._schedule_downgrade(subscription, current_plan, new_plan, user_id, now=now)

    async def cancel_pending_change(self, tenant_id: uuid.UUID) -> PlanChangeHistory:
        """AC3 — rezygnacja z zaplanowanego downgrade przed końcem okresu.

        Bez żadnego wywołania tpay: ``cancel_at_period_end = false``,
        przywrócone ``next_charge_at`` = koniec okresu.
        """
        pending = await self.get_pending_change(tenant_id)
        if pending is None:
            raise NotFoundError("Brak oczekującej zmiany planu")
        subscription = await self.get_current_subscription(tenant_id)
        if subscription is not None:
            self._revert_pending(pending, subscription)
        else:
            pending.status = PlanChangeStatus.CANCELED
        await self._db.flush()
        return pending

    async def get_pending_change(self, tenant_id: uuid.UUID) -> PlanChangeHistory | None:
        result = await self._db.execute(
            select(PlanChangeHistory).where(
                PlanChangeHistory.tenant_id == tenant_id,
                PlanChangeHistory.status == PlanChangeStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def get_change_history(self, tenant_id: uuid.UUID) -> list[PlanChangeHistory]:
        """AC4 — historia zmian planu tenanta (najnowsze pierwsze)."""
        result = await self._db.execute(
            select(PlanChangeHistory)
            .where(PlanChangeHistory.tenant_id == tenant_id)
            .order_by(PlanChangeHistory.requested_at.desc())
        )
        return list(result.scalars().all())

    async def finalize_plan_upgrade(self, txn: PaymentTransaction) -> None:
        """AC1 — finalizacja upgrade po webhooku ``paid`` (source=plan_change).

        Plan zmieniany natychmiast; przy płatny→płatny ``current_period_end``
        bez zmian (pełna stawka od kolejnego cyklu), przy Freemium→płatny nowy
        okres od dnia zakupu. Czyści stan dunningu/grace (upgrade w grace —
        edge 6.5). Liczniki użycia zachowane (nie dotykamy UsageCounter).
        """
        meta = txn.meta or {}
        try:
            new_plan = PlanName(meta.get("plan"))
            from_plan = PlanName(meta.get("from_plan"))
        except ValueError:
            logger.error("finalize_plan_upgrade: nieprawidłowe meta %r (order %s)", meta, txn.hidden_description)
            return

        plan_result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == new_plan))
        plan = plan_result.scalar_one_or_none()
        if plan is None:
            raise LookupError(f"Plan {new_plan} nie istnieje — uruchom seed planów (seed_subscription_plans)")

        subscription = await self.get_current_subscription(txn.tenant_id)
        if subscription is None:
            logger.error(
                "finalize_plan_upgrade: brak subskrypcji tenanta %s (order %s)", txn.tenant_id, txn.hidden_description
            )
            return

        now = datetime.now(UTC)
        subscription.plan_id = plan.id
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.cancel_at_period_end = False
        if from_plan == PlanName.FREEMIUM:
            # AC1: Freemium→płatny — nowy okres od dnia zakupu.
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=30)
        subscription.next_charge_at = subscription.current_period_end
        # Upgrade w grace/dunningu (edge 6.5) — czyścimy stan windykacji.
        subscription.dunning_attempt = 0
        subscription.dunning_next_retry_at = None
        subscription.grace_until = None
        subscription.previous_plan_id = None

        change = await self._change_by_id(meta.get("change_id"))
        if change is not None:
            change.status = PlanChangeStatus.COMPLETED
            change.effective_at = now

        await self._db.execute(update(Tenant).where(Tenant.id == txn.tenant_id).values(plan=new_plan))
        await self._db.flush()
        logger.info(
            "Upgrade planu sfinalizowany: tenant=%s %s→%s (order %s)",
            txn.tenant_id,
            from_plan.value,
            new_plan.value,
            txn.hidden_description,
        )
        await _emit_subscription_changed(
            txn.tenant_id, from_plan.value, new_plan.value, subscription.current_period_start
        )

    async def cancel_failed_plan_change(self, txn: PaymentTransaction) -> None:
        """Edge 6.5 — nieudana płatność upgrade: rekord ``canceled``,
        tenant zostaje na planie dotychczasowym (plan nie był zmieniany)."""
        change = await self._change_by_id((txn.meta or {}).get("change_id"))
        if change is None or change.status != PlanChangeStatus.PENDING:
            return
        change.status = PlanChangeStatus.CANCELED
        await self._db.flush()
        logger.warning(
            "Upgrade planu anulowany po nieudanej płatności: tenant=%s order=%s",
            txn.tenant_id,
            txn.hidden_description,
        )

    async def execute_scheduled_downgrade(
        self, subscription: Subscription, *, now: datetime
    ) -> SubscriptionPlan | None:
        """AC6 — egzekucja zaplanowanego downgradu po ``current_period_end``.

        Plan docelowy z oczekującego rekordu history (fallback: Freemium —
        anulowanie bez rekordu, 7.7). Czyści flagę; do Freemium — koniec
        obciążeń; do planu płatnego — odnowienie wymagalne od razu (ciągłość
        rozliczeń przez zwykłą ścieżkę odnowień 7.2).
        """
        pending = await self.get_pending_change(subscription.tenant_id)
        target_name = pending.to_plan if pending is not None else PlanName.FREEMIUM
        previous_name = pending.from_plan if pending is not None else None

        plan_result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == target_name))
        target = plan_result.scalar_one_or_none()
        if target is None:
            logger.error("Egzekucja downgradu: plan %s nie istnieje — pomijam", target_name)
            return None

        period_end = subscription.current_period_end
        subscription.plan_id = target.id
        subscription.cancel_at_period_end = False
        if target_name == PlanName.FREEMIUM:
            subscription.next_charge_at = None
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=30)
        else:
            # Płatny plan docelowy: obciążenie w najbliższym przebiegu odnowień
            # (renew_subscription przedłuży okres od current_period_end).
            subscription.next_charge_at = period_end

        if pending is not None:
            pending.status = PlanChangeStatus.COMPLETED
            pending.effective_at = now

        # Legacy kolumna tenants.plan (gating modułów) — spójność z subskrypcją.
        await self._db.execute(update(Tenant).where(Tenant.id == subscription.tenant_id).values(plan=target_name))
        await self._db.flush()
        logger.info(
            "Downgrade wykonany: tenant=%s → %s (koniec okresu %s)",
            subscription.tenant_id,
            target_name.value,
            period_end,
        )
        await _emit_subscription_changed(
            subscription.tenant_id,
            previous_name.value if previous_name else None,
            target_name.value,
            now,
        )
        return target

    # --- Story 7.7: portal billingowy (AC2-AC5) ---

    async def _plan_by_id(self, plan_id: uuid.UUID) -> SubscriptionPlan | None:
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        return result.scalar_one_or_none()

    async def get_subscription_details(self, tenant_id: uuid.UUID) -> SubscriptionDetail:
        """AC3 — pełne dane subskrypcji dla portalu: plan (nazwa/cena), metoda
        płatności (``PaymentToken``), zaplanowany downgrade (7.5) i stan
        windykacji (``grace_until`` dla bannera FE)."""
        subscription = await self.get_current_subscription(tenant_id)
        if subscription is None:
            raise NotFoundError("Subscription not found")

        plan = await self._plan_by_id(subscription.plan_id)

        payment_method = None
        if subscription.payment_token_id is not None:
            result = await self._db.execute(
                select(PaymentToken).where(PaymentToken.id == subscription.payment_token_id)
            )
            payment_method = result.scalar_one_or_none()

        pending = await self.get_pending_change(tenant_id)
        return SubscriptionDetail(
            subscription=subscription,
            plan=plan,
            payment_method=payment_method,
            pending_change=pending,
        )

    async def cancel_subscription(self, tenant_id: uuid.UUID) -> Subscription:
        """AC4 — anulowanie subskrypcji, wyłącznie lokalne (§3.5 — bez API tpay).

        ``cancel_at_period_end = True`` + ``next_charge_at = None`` (stop
        obciążeń); dostęp utrzymany do końca okresu, potem scheduler egzekwuje
        powrót (fallback: Freemium; przy zaplanowanym downgrade 7.5 — plan
        docelowy z rekordu history, AC4: „lub niższego”). Freemium nie podlega
        anulowaniu; stan windykacji (past_due) wymaga wyjaśnienia najpierw.
        """
        subscription = await self._get_subscription_locked(tenant_id)
        if subscription is None:
            raise NotFoundError("Subscription not found")
        pending = await self.get_pending_change(tenant_id)
        plan = await self._plan_by_id(subscription.plan_id)

        if plan is not None and plan.name == PlanName.FREEMIUM:
            raise ConflictError("Plan Freemium jest aktywny bezterminowo — nie podlega anulowaniu")
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise ConflictError("Subskrypcja nie jest aktywna — najpierw wyjaśnij stan płatności (windykacja)")
        if subscription.cancel_at_period_end:
            if pending is not None:
                # Zaplanowany downgrade (7.5) już zatrzymał obciążenia — powrót
                # na koniec okresu do planu niższego; operacja idempotentna.
                return subscription
            raise ConflictError("Subskrypcja jest już anulowana — aktywna do końca okresu")

        subscription.cancel_at_period_end = True
        subscription.next_charge_at = None
        await self._db.flush()
        logger.info("Subskrypcja anulowana (aktywna do końca okresu): tenant=%s", tenant_id)
        return subscription

    async def reactivate_subscription(self, tenant_id: uuid.UUID) -> Subscription:
        """AC5 — reaktywacja anulowanej subskrypcji, lokalnie (bez API tpay).

        Zdejmuje ``cancel_at_period_end`` i przywraca ``next_charge_at`` na
        koniec bieżącego okresu (ciągłość bez przerwy). Sprzeczna z zaplanowanym
        downgrade (7.5) — najpierw anuluj zaplanowaną zmianę planu.
        """
        subscription = await self._get_subscription_locked(tenant_id)
        if subscription is None:
            raise NotFoundError("Subscription not found")
        if await self.get_pending_change(tenant_id) is not None:
            raise ConflictError("Masz zaplanowaną zmianę planu — najpierw anuluj zaplanowaną zmianę")
        if not subscription.cancel_at_period_end:
            raise ConflictError("Subskrypcja nie jest anulowana")
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise ConflictError("Subskrypcja nie jest aktywna — najpierw wyjaśnij stan płatności")
        if subscription.current_period_end <= datetime.now(UTC):
            raise ConflictError("Okres subskrypcji już się zakończył — nie można reaktywować")

        subscription.cancel_at_period_end = False
        subscription.next_charge_at = subscription.current_period_end
        await self._db.flush()
        logger.info("Subskrypcja reaktywowana: tenant=%s", tenant_id)
        return subscription

    async def get_transactions(
        self,
        tenant_id: uuid.UUID,
        *,
        status: PaymentStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[TransactionListItem], int]:
        """AC2 — historia transakcji malejąco po dacie, z filtrami i paginacją.

        Metoda płatności: z faktury (``Invoice.payment_method`` — karta/BLIK/
        przelew), fallback BLIK po ``meta.blik_alias_value`` (korelacja 7.3),
        inaczej ``None`` (FE pokazuje „—”). RLS + jawny filtr tenant_id;
        faktury pobierane zbiorczo dla strony (bez N+1).
        """
        conditions = [PaymentTransaction.tenant_id == tenant_id]
        if status is not None:
            conditions.append(PaymentTransaction.status == status)
        if date_from is not None:
            conditions.append(
                PaymentTransaction.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
            )
        if date_to is not None:
            conditions.append(
                PaymentTransaction.created_at
                < datetime.combine(date_to, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)
            )

        total = (
            await self._db.execute(select(func.count()).select_from(PaymentTransaction).where(*conditions))
        ).scalar_one()
        rows = (
            (
                await self._db.execute(
                    select(PaymentTransaction)
                    .where(*conditions)
                    .order_by(PaymentTransaction.created_at.desc())
                    .offset((page - 1) * size)
                    .limit(size)
                )
            )
            .scalars()
            .all()
        )

        invoices_by_txn: dict[uuid.UUID, Invoice] = {}
        tx_ids = [t.id for t in rows]
        if tx_ids:
            inv_rows = await self._db.execute(select(Invoice).where(Invoice.payment_id.in_(tx_ids)))
            for invoice in inv_rows.scalars().all():
                invoices_by_txn[invoice.payment_id] = invoice

        items: list[TransactionListItem] = []
        for txn in rows:
            invoice = invoices_by_txn.get(txn.id)
            if invoice is not None:
                method: str | None = invoice.payment_method.value
            elif (txn.meta or {}).get("blik_alias_value"):
                method = "blik"
            else:
                method = None
            items.append(TransactionListItem(transaction=txn, method=method, invoice=invoice))
        return items, total

    async def _start_upgrade(
        self,
        subscription: Subscription,
        current_plan: SubscriptionPlan,
        new_plan: PlanName,
        user_id: uuid.UUID | None,
        *,
        now: datetime,
        provider,
        owner_email: str,
        owner_name: str | None,
    ) -> PlanChangeResult:
        details = calculate_proration(
            current_plan=current_plan.name,
            new_plan=new_plan,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            now=now,
            current_price=plan_monthly_price(current_plan.name),
            new_price=plan_monthly_price(new_plan),
        )
        amount = Decimal(details["amount"])

        history = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=subscription.tenant_id,
            from_plan=current_plan.name,
            to_plan=new_plan,
            change_type=PlanChangeType.UPGRADE,
            requested_at=now,
            requested_by=user_id,
            status=PlanChangeStatus.PENDING,
            proration_details=details,
        )
        self._db.add(history)

        if amount <= Decimal("0.00"):
            # AC1: prorated ≤ 0,00 (np. ostatni dzień okresu) — bez obciążenia,
            # pełna stawka w kolejnym cyklu.
            await self._apply_free_upgrade(subscription, new_plan, history, now=now)
            return PlanChangeResult(
                change=history,
                change_type=PlanChangeType.UPGRADE,
                amount=amount,
                payment_required=False,
            )

        order_id = str(uuid.uuid4())
        billing = get_billing_settings()
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=subscription.tenant_id,
            provider="tpay",
            hidden_description=order_id,
            amount=amount,
            currency=billing.billing_currency,
            status=PaymentStatus.PENDING,
            meta={
                "plan": new_plan.value,
                "from_plan": current_plan.name.value,
                "source": "plan_change",
                "change_id": str(history.id),
                "payer_email": owner_email,
                "proration": details,
            },
        )
        self._db.add(txn)
        await self._db.flush()

        token = await self._active_subscription_token(subscription)
        description = f"TestGEN — zmiana planu na {new_plan.capitalize()} (prorated)"
        if token is not None:
            # Zapisana metoda (7.2) — obciążenie merchant-initiated bez redirectu.
            value = decrypt_token_value(token.tenant_id, token.value_encrypted)
            try:
                result = await provider.charge_recurring(
                    amount=amount,
                    currency=billing.billing_currency,
                    description=description,
                    order_id=order_id,
                    payer_email=owner_email,
                    card_token=value if token.kind == TokenKind.CARD_TOKEN else None,
                    blik_alias=value if token.kind in (TokenKind.BLIK_ALIAS_PAYID, TokenKind.BLIK_ALIAS_UID) else None,
                )
            except Exception:
                await self._db.delete(txn)
                history.status = PlanChangeStatus.CANCELED
                await self._db.flush()
                logger.exception("Obciążenie prorated nie powiodło się (tenant %s)", subscription.tenant_id)
                raise
            txn.transaction_id = result.transaction_id
            await self._db.flush()
            return PlanChangeResult(
                change=history,
                change_type=PlanChangeType.UPGRADE,
                amount=amount,
                payment_required=True,
                order_id=order_id,
            )

        # Brak zapisanej metody — checkout redirect (7.4) z kwotą prorated.
        try:
            checkout = await provider.create_checkout(
                amount=amount,
                currency=billing.billing_currency,
                description=description,
                order_id=order_id,
                payer_email=owner_email,
                payer_name=owner_name,
            )
        except Exception:
            await self._db.delete(txn)
            history.status = PlanChangeStatus.CANCELED
            await self._db.flush()
            logger.exception("Checkout upgrade nie powiódł się (tenant %s)", subscription.tenant_id)
            raise
        txn.transaction_id = checkout.transaction_id
        await self._db.flush()
        return PlanChangeResult(
            change=history,
            change_type=PlanChangeType.UPGRADE,
            amount=amount,
            payment_required=True,
            payment_url=checkout.transaction_payment_url,
            order_id=order_id,
        )

    async def _schedule_downgrade(
        self,
        subscription: Subscription,
        current_plan: SubscriptionPlan,
        new_plan: PlanName,
        user_id: uuid.UUID | None,
        *,
        now: datetime,
    ) -> PlanChangeResult:
        """AC2 — czysto lokalna operacja (§3.5): NIE wołamy API tpay."""
        subscription.cancel_at_period_end = True
        subscription.next_charge_at = None  # stop kolejnego obciążenia

        history = PlanChangeHistory(
            id=uuid.uuid4(),
            tenant_id=subscription.tenant_id,
            from_plan=current_plan.name,
            to_plan=new_plan,
            change_type=PlanChangeType.DOWNGRADE,
            effective_at=subscription.current_period_end,
            requested_at=now,
            requested_by=user_id,
            status=PlanChangeStatus.PENDING,
            proration_details={},  # bez komponentu prorated (AC2)
        )
        self._db.add(history)
        await self._db.flush()
        logger.info(
            "Downgrade zaplanowany: tenant=%s %s→%s od %s",
            subscription.tenant_id,
            current_plan.name.value,
            new_plan.value,
            subscription.current_period_end,
        )
        return PlanChangeResult(
            change=history,
            change_type=PlanChangeType.DOWNGRADE,
            amount=Decimal("0.00"),
            payment_required=False,
        )

    async def _apply_free_upgrade(
        self,
        subscription: Subscription,
        new_plan: PlanName,
        history: PlanChangeHistory,
        *,
        now: datetime,
    ) -> None:
        """Upgrade bez obciążenia (kwota ≤ 0,00) — natychmiastowa zmiana planu."""
        plan_result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == new_plan))
        plan = plan_result.scalar_one_or_none()
        if plan is None:
            raise LookupError(f"Plan {new_plan} nie istnieje — uruchom seed planów (seed_subscription_plans)")
        subscription.plan_id = plan.id
        subscription.next_charge_at = subscription.current_period_end
        history.status = PlanChangeStatus.COMPLETED
        history.effective_at = now
        await self._db.execute(update(Tenant).where(Tenant.id == subscription.tenant_id).values(plan=new_plan))
        await self._db.flush()

    def _revert_pending(self, pending: PlanChangeHistory, subscription: Subscription) -> None:
        """Cofnięcie oczekującej zmiany: status canceled + przywrócony harmonogram."""
        pending.status = PlanChangeStatus.CANCELED
        if pending.change_type == PlanChangeType.DOWNGRADE:
            subscription.cancel_at_period_end = False
            subscription.next_charge_at = subscription.current_period_end

    async def _get_subscription_locked(self, tenant_id: uuid.UUID) -> Subscription | None:
        """Serializacja zmian per-tenant (Dev Notes) — FOR UPDATE na wierszu."""
        result = await self._db.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def _plan_of(self, subscription: Subscription) -> SubscriptionPlan:
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id))
        plan = result.scalar_one_or_none()
        if plan is None:
            raise LookupError(f"Plan {subscription.plan_id} nie istnieje — niespójność danych subskrypcji")
        return plan

    async def _active_subscription_token(self, subscription: Subscription) -> PaymentToken | None:
        if subscription.payment_token_id is None:
            return None
        result = await self._db.execute(select(PaymentToken).where(PaymentToken.id == subscription.payment_token_id))
        token = result.scalar_one_or_none()
        if token is None or token.tpay_status != TpayTokenStatus.ACTIVE:
            return None
        return token

    async def _change_by_id(self, change_id: str | None) -> PlanChangeHistory | None:
        if not change_id:
            return None
        try:
            change_uuid = uuid.UUID(change_id)
        except ValueError:
            return None
        result = await self._db.execute(select(PlanChangeHistory).where(PlanChangeHistory.id == change_uuid))
        return result.scalar_one_or_none()

    async def _link_default_method(self, tenant_id: uuid.UUID, token: PaymentToken) -> None:
        """Powiązanie metody z subskrypcją (AC1) — pierwsza metoda = domyślna.

        ``is_default`` jest mirrorem ``subscription.payment_token_id`` (jedno
        źródło prawdy wiązania; kolumna utrzymywana dla listowania UI).
        """
        subscription = await self.get_current_subscription(tenant_id)
        if subscription is None:
            return
        if subscription.payment_token_id is None:
            subscription.payment_token_id = token.id
            token.is_default = True
        await self._db.flush()
