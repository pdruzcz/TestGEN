"""SubscriptionScheduler — odnowienia cykliczne + dunning + grace (Story 7.2).

tpay nie ma silnika subskrypcji (D2) — harmonogram odnowień jest nasz.
Zadanie Celery beat **co dobę** (``app.workers.tasks.billing_tasks``) skanuje
subskrypcje płatne, których ``next_charge_at <= dziś`` i``dunning_next_retry_at``
(cooldown) nie blokuje, obciąża zapisaną metodą (merchant-initiated: karta
``pay.cardPaymentData.token`` / BLIK alias ``blikPaymentData.type = 2``)
i tworzy ``PaymentTransaction`` (pending) na tej samej ścieżce webhooka co 7.4.
Porażka → dunning (D+1/D+3/D+5 → downgrade do Freemium z grace 7 dni, CR#2).
Drugi przebieg skanuje wygasłe grace (``enforce_grace_expiry``).

Kontekst RLS: przepływ systemowy (bez JWT) — ``SET LOCAL app.current_tenant``
na NIL UUID ustawia wrapper Celery (wzorzec WebhookProcessor).
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentStatus, PaymentToken, PaymentTransaction, TokenKind, TpayTokenStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant
from app.services.billing.providers.base import PaymentProvider
from app.services.billing.providers.tpay.client import TpayApiError
from app.services.billing.subscription_service import SubscriptionService, decrypt_token_value

logger = logging.getLogger(__name__)

# Cooldown ciszy po utworzeniu obciążenia: jeżeli webhook `paid` nie nadejdzie
# (awaria notyfikacji), skan nie strzeli drugiego obciążenia tego samego dnia.
# Webhook paid czyści stan (renew_subscription); spóźniona odmowa przełącza
# w właściwy harmonogram dunningu (register_failed_charge).
_SILENCE_COOLDOWN_DAYS = 1


class SubscriptionScheduler:
    """Jednorazowy przebieg odnowień — wywoływany z beat, testowalny wprost."""

    def __init__(self, db: AsyncSession, provider: PaymentProvider) -> None:
        self._db = db
        self._provider = provider
        self._svc = SubscriptionService(db)

    async def run(self, *, now: datetime | None = None) -> dict[str, int]:
        now = now or datetime.now(UTC)
        stats: dict[str, int] = {}

        # Oba skany z góry (spójny obraz), potem przetwarzanie.
        due = await self._db.execute(
            select(Subscription)
            .where(
                Subscription.next_charge_at.is_not(None),
                Subscription.next_charge_at <= now,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.cancel_at_period_end.is_(False),
                # Cooldown (dunning retry / silence-guard) blokuje podwójny przebieg.
                or_(
                    Subscription.dunning_next_retry_at.is_(None),
                    Subscription.dunning_next_retry_at <= now,
                ),
            )
            .order_by(Subscription.next_charge_at)
            # AC5: seria zablokowana per-tenant — równoległy beat pomija wiersz.
            .with_for_update(skip_locked=True)
        )
        due_subs = list(due.scalars().all())

        expired = await self._db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.PAST_DUE,
                Subscription.grace_until.is_not(None),
                Subscription.grace_until <= now,
            )
        )
        expired_subs = list(expired.scalars().all())

        # 7.5 AC6: zaplanowane downgrade'y wymagalne po końcu okresu.
        downgrades = await self._db.execute(
            select(Subscription)
            .where(
                Subscription.cancel_at_period_end.is_(True),
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.current_period_end <= now,
            )
            .with_for_update(skip_locked=True)
        )
        downgrade_subs = list(downgrades.scalars().all())

        for subscription in due_subs:
            outcome = await self._process_renewal(subscription, now)
            stats[outcome] = stats.get(outcome, 0) + 1

        for subscription in expired_subs:
            await self._svc.enforce_grace_expiry(subscription)
            stats["grace_expired"] = stats.get("grace_expired", 0) + 1

        for subscription in downgrade_subs:
            outcome = await self._process_scheduled_downgrade(subscription, now)
            stats[outcome] = stats.get(outcome, 0) + 1

        if stats:
            logger.info("SubscriptionScheduler: %s", stats)
        return stats

    async def _process_renewal(self, subscription: Subscription, now: datetime) -> str:
        plan_result = await self._db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
        )
        plan = plan_result.scalar_one_or_none()
        if plan is None:
            logger.error("Odnowienie: plan %s nie istnieje — pomijam", subscription.plan_id)
            return "skipped"

        token: PaymentToken | None = None
        if subscription.payment_token_id is not None:
            token_result = await self._db.execute(
                select(PaymentToken).where(PaymentToken.id == subscription.payment_token_id)
            )
            token = token_result.scalar_one_or_none()

        owner_email = await self._owner_email(subscription.tenant_id)

        if token is None or token.tpay_status != TpayTokenStatus.ACTIVE:
            logger.warning(
                "Odnowienie tenanta %s bez aktywnej metody płatności (token=%s) — dunning",
                subscription.tenant_id,
                subscription.payment_token_id,
            )
            await self._svc.register_failed_charge(subscription, owner_email=owner_email)
            return "failed"

        value = decrypt_token_value(token.tenant_id, token.value_encrypted)
        order_id = str(uuid.uuid4())
        txn = PaymentTransaction(
            id=uuid.uuid4(),
            tenant_id=subscription.tenant_id,
            provider="tpay",
            hidden_description=order_id,
            amount=plan.price_monthly,
            currency=plan.currency,
            status=PaymentStatus.PENDING,
            meta={"plan": plan.name, "source": "recurring", "payer_email": owner_email},
        )
        self._db.add(txn)
        await self._db.flush()

        try:
            result = await self._provider.charge_recurring(
                amount=plan.price_monthly,
                currency=plan.currency,
                description=f"TestGEN — odnowienie subskrypcji {plan.display_name} (miesięczna)",
                order_id=order_id,
                payer_email=owner_email or "billing@testgen.local",
                card_token=value if token.kind == TokenKind.CARD_TOKEN else None,
                blik_alias=value if token.kind in (TokenKind.BLIK_ALIAS_PAYID, TokenKind.BLIK_ALIAS_UID) else None,
            )
        except TpayApiError:
            # Transakcja nigdy nie powstała u tpay — cofamy lokalny pending.
            await self._db.delete(txn)
            logger.exception("Obciążenie cykliczne nie powiodło się (tenant %s)", subscription.tenant_id)
            await self._svc.register_failed_charge(subscription, owner_email=owner_email)
            return "failed"

        txn.transaction_id = result.transaction_id
        subscription.dunning_next_retry_at = now + timedelta(days=_SILENCE_COOLDOWN_DAYS)
        await self._db.flush()
        logger.info(
            "Obciążenie cykliczne utworzone: tenant=%s order=%s txn=%s",
            subscription.tenant_id,
            order_id,
            result.transaction_id,
        )
        return "charged"

    async def _process_scheduled_downgrade(self, subscription: Subscription, now: datetime) -> str:
        """7.5 AC6 — egzekucja downgradu po ``current_period_end`` + email.

        Plan docelowy z oczekującego rekordu ``plan_change_history``
        (fallback Freemium). Powiadomienie best-effort — porażka emaila
        nie przerywa przebiegu (in-app: brak infrastruktury, patrz story).
        """
        old_plan_result = await self._db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == subscription.plan_id)
        )
        old_plan = old_plan_result.scalar_one_or_none()

        target = await self._svc.execute_scheduled_downgrade(subscription, now=now)
        if target is None:
            return "downgrade_skipped"

        owner_email = await self._owner_email(subscription.tenant_id)
        if owner_email:
            _send_plan_changed_email_safely(
                owner_email,
                from_plan=old_plan.display_name if old_plan else "?",
                to_plan=target.display_name,
            )
        return "downgraded"

    async def _owner_email(self, tenant_id: uuid.UUID) -> str | None:
        """Email Ownera tenanta — adresat powiadomień dunningu (AC6)."""
        result = await self._db.execute(
            select(User.email)
            .join(UserTenant, UserTenant.user_id == User.id)
            .where(UserTenant.tenant_id == tenant_id, UserTenant.role == TenantRole.OWNER)
            .limit(1)
        )
        return result.scalar_one_or_none()


def _send_plan_changed_email_safely(email: str, *, from_plan: str, to_plan: str) -> None:
    """Email zmiany planu (7.5 AC6) — best-effort, nie wywala schedulera."""
    from app.services.email.email_service import send_plan_changed_email

    try:
        send_plan_changed_email(email, from_plan, to_plan)
    except Exception:
        logger.warning("Email zmiany planu dla %s nie wysłany — scheduler kontynuuje", email, exc_info=True)
