"""Testy tokenów płatności — Story 7.2 (AC1, AC2, AC3; Task 8.1).

PaymentToken: szyfrowanie AES-256-GCM per-tenant (wzorzec 1.54), zapis
z webhooka transakcyjnego (card_token), zapis z notyfikacji JSON rejestracji
(``data.token``), usuwanie z guardem 409 na ostatnią metodę, listowanie.
DB mockowana (wzorzec test_billing_checkout).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import inspect

from app.core.exceptions import ConflictError
from app.models.payment import PaymentToken, TokenKind, TpayTokenStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.services.billing.subscription_service import (
    decrypt_token_value,
    encrypt_token_value,
    token_digest,
)


def _columns(model) -> dict[str, object]:
    return {c.name: c for c in inspect(model).columns}


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
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        next_charge_at=now + timedelta(days=30),
        cancel_at_period_end=False,
    )
    fields.update(kw)
    return Subscription(**fields)


class TestPaymentTokenModel:
    """Task 1.1 — kształt tabeli payment_tokens."""

    def test_tablename(self):
        assert PaymentToken.__tablename__ == "payment_tokens"

    def test_columns_present(self):
        cols = _columns(PaymentToken)
        for name in (
            "id",
            "tenant_id",
            "kind",
            "value_encrypted",
            "value_digest",
            "card_tail",
            "card_brand",
            "expires_at",
            "tpay_status",
            "is_default",
            "registration_id",
            "created_at",
            "updated_at",
        ):
            assert name in cols, f"brak kolumny {name}"

    def test_token_kind_enum_values(self):
        assert {k.value for k in TokenKind} == {"card_token", "blik_alias_uid", "blik_alias_payid"}

    def test_tpay_token_status_enum_values(self):
        # PENDING — rejestracja /tokens przed notyfikacją data.token (AC2)
        assert {s.value for s in TpayTokenStatus} == {"pending", "active", "suspended", "deleted"}

    def test_subscription_dunning_columns(self):
        """Task 1.2/6.1 — FK metody płatności + pola dunningu w Subscription."""
        cols = _columns(Subscription)
        for name in (
            "payment_token_id",
            "dunning_attempt",
            "dunning_next_retry_at",
            "grace_until",
            "previous_plan_id",
        ):
            assert name in cols, f"brak kolumny {name}"


class TestTokenCrypto:
    """AC1 — AES-256-GCM per-tenant (reaktywacja wzorca 1.54)."""

    def test_roundtrip(self):
        tenant = uuid.uuid4()
        blob = encrypt_token_value(tenant, "tbe_abc123")
        assert isinstance(blob, bytes)
        assert decrypt_token_value(tenant, blob) == "tbe_abc123"

    def test_cross_tenant_decrypt_fails(self):
        """Token tenanta A nie odszyfrowuje się kontekstem tenanta B."""
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        blob = encrypt_token_value(tenant_a, "tbe_secret")
        with pytest.raises(InvalidTag):
            decrypt_token_value(tenant_b, blob)

    def test_nonce_randomized(self):
        """Ta sama wartość szyfrowana dwa razy daje różne bloby (GCM nonce)."""
        tenant = uuid.uuid4()
        assert encrypt_token_value(tenant, "x") != encrypt_token_value(tenant, "x")

    def test_digest_deterministic_and_scoped(self):
        """Digest = lookup po wartości (GCM losowe → nie da się szukać po blobie)."""
        tenant = uuid.uuid4()
        assert token_digest(tenant, "tbe_1") == token_digest(tenant, "tbe_1")
        assert token_digest(tenant, "tbe_1") != token_digest(uuid.uuid4(), "tbe_1")
        assert token_digest(tenant, "tbe_1") != token_digest(tenant, "tbe_2")


class TestSaveCardTokenFromWebhook:
    """AC1 — webhook transakcyjny z card_token/card_tail/card_brand (save=1)."""

    async def test_saves_active_card_token_and_links_subscription(self):
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        basic = _plan()
        sub = _sub(basic, tenant_id=tenant_id)
        db = AsyncMock()
        # 1) SELECT PaymentToken po digest, 2) SELECT Subscription
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(sub)])

        svc = SubscriptionService(db)
        token = await svc.save_card_token_from_webhook(
            tenant_id=tenant_id,
            token_value="tbe_xyz",
            card_tail="4242",
            card_brand="visa",
        )

        assert token.kind == TokenKind.CARD_TOKEN
        assert token.tpay_status == TpayTokenStatus.ACTIVE
        assert token.card_tail == "4242"
        assert token.card_brand == "visa"
        assert decrypt_token_value(tenant_id, token.value_encrypted) == "tbe_xyz"
        # powiązanie z subskrypcją jako aktywna metoda (AC1)
        assert sub.payment_token_id == token.id
        db.add.assert_called_once()

    async def test_idempotent_on_same_token_value(self):
        """Ponowna notyfikacja z tym samym tokenem nie dubluje rekordu."""
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        existing = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=TokenKind.CARD_TOKEN,
            value_encrypted=b"blob",
            value_digest=token_digest(tenant_id, "tbe_dup"),
            tpay_status=TpayTokenStatus.ACTIVE,
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(existing)])

        svc = SubscriptionService(db)
        token = await svc.save_card_token_from_webhook(
            tenant_id=tenant_id, token_value="tbe_dup", card_tail="1111", card_brand="mastercard"
        )
        assert token.id == existing.id
        db.add.assert_not_called()


class TestSaveCardTokenFromNotification:
    """AC2/Task 3.3 — notyfikacja JSON `data.token` po rejestracji bez obciążenia."""

    async def test_confirms_pending_registration(self):
        """Rekord PENDING (z POST /payment-methods) z registration_id → ACTIVE."""
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        pending = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=TokenKind.CARD_TOKEN,
            tpay_status=TpayTokenStatus.PENDING,
            registration_id="reg-123",
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(pending)])

        svc = SubscriptionService(db)
        token = await svc.save_card_token_from_notification(
            tenant_id=tenant_id,
            token_value="tbe_new",
            registration_id="reg-123",
            card_tail="0000",
            card_brand="visa",
        )
        assert token.id == pending.id
        assert token.tpay_status == TpayTokenStatus.ACTIVE
        assert decrypt_token_value(tenant_id, token.value_encrypted) == "tbe_new"
        assert token.value_digest == token_digest(tenant_id, "tbe_new")
        db.add.assert_not_called()  # update istniejącego, nie nowy rekord

    async def test_creates_when_no_pending_registration(self):
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None)])

        svc = SubscriptionService(db)
        token = await svc.save_card_token_from_notification(
            tenant_id=tenant_id, token_value="tbe_orphan", card_tail="9999", card_brand="visa"
        )
        assert token.tpay_status == TpayTokenStatus.ACTIVE
        db.add.assert_called_once()


class TestDeletePaymentMethod:
    """AC3 — DELETE: soft delete + 409 na ostatnią metodę przy aktywnej subskrypcji."""

    def _token(self, tenant_id, status=TpayTokenStatus.ACTIVE) -> PaymentToken:
        return PaymentToken(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=TokenKind.CARD_TOKEN,
            value_encrypted=b"blob",
            tpay_status=status,
        )

    async def test_delete_last_method_with_active_recurring_conflicts(self):
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        token = self._token(tenant_id)
        basic = _plan()
        sub = _sub(basic, tenant_id=tenant_id, payment_token_id=token.id)
        db = AsyncMock()
        # token, pozostałe aktywne metody, subskrypcja
        db.execute = AsyncMock(side_effect=[_scalar(token), _scalars([]), _scalar(sub)])

        svc = SubscriptionService(db)
        with pytest.raises(ConflictError):
            await svc.delete_payment_method(tenant_id, token.id)

    async def test_delete_ok_when_other_methods_remain(self):
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        token = self._token(tenant_id)
        other = self._token(tenant_id)
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(token), _scalars([other]), _scalar(None)])

        svc = SubscriptionService(db)
        deleted = await svc.delete_payment_method(tenant_id, token.id)
        assert deleted.tpay_status == TpayTokenStatus.DELETED  # soft delete lokalny

    async def test_delete_ok_when_subscription_not_recurring(self):
        """cancel_at_period_end / brak next_charge_at → metoda niepotrzebna."""
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        token = self._token(tenant_id)
        basic = _plan()
        sub = _sub(basic, tenant_id=tenant_id, payment_token_id=token.id, cancel_at_period_end=True)
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(token), _scalars([]), _scalar(sub)])

        svc = SubscriptionService(db)
        deleted = await svc.delete_payment_method(tenant_id, token.id)
        assert deleted.tpay_status == TpayTokenStatus.DELETED

    async def test_delete_not_found_raises(self):
        from app.core.exceptions import NotFoundError
        from app.services.billing.subscription_service import SubscriptionService

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(None)])
        with pytest.raises(NotFoundError):
            await SubscriptionService(db).delete_payment_method(uuid.uuid4(), uuid.uuid4())


class TestListPaymentMethods:
    """AC3 — lista metod: rodzaj, tail, brand, status, domyślna."""

    async def test_list_returns_tokens(self):
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        tokens = [
            PaymentToken(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                kind=TokenKind.CARD_TOKEN,
                tpay_status=TpayTokenStatus.ACTIVE,
                card_tail="4242",
                card_brand="visa",
                is_default=True,
            ),
        ]
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalars(tokens)])

        methods = await SubscriptionService(db).list_payment_methods(tenant_id)
        assert len(methods) == 1
        assert methods[0].kind == TokenKind.CARD_TOKEN
        assert methods[0].card_tail == "4242"
        assert methods[0].is_default is True


class TestSaveBlikAliasFromNotification:
    """AC4 — notyfikacja ALIAS_REGISTER → PaymentToken kind=blik_alias_payid."""

    async def test_creates_payid_alias_token(self):
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        db = AsyncMock()
        # digest (dedup) → brak; subscription → brak
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None)])

        svc = SubscriptionService(db)
        token = await svc.save_blik_alias_from_notification(tenant_id, alias_value="777123456")
        assert token.kind == TokenKind.BLIK_ALIAS_PAYID
        assert token.tpay_status == TpayTokenStatus.ACTIVE
        assert decrypt_token_value(tenant_id, token.value_encrypted) == "777123456"

    async def test_creates_uid_alias_token_when_type_uid(self):
        """+ blik_alias_uid jeśli dotyczy (AC4)."""
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None)])

        token = await SubscriptionService(db).save_blik_alias_from_notification(
            tenant_id, alias_value="uid-x", kind=TokenKind.BLIK_ALIAS_UID
        )
        assert token.kind == TokenKind.BLIK_ALIAS_UID

    async def test_idempotent_on_same_alias(self):
        from app.services.billing.subscription_service import SubscriptionService

        tenant_id = uuid.uuid4()
        existing = PaymentToken(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=TokenKind.BLIK_ALIAS_PAYID,
            value_encrypted=b"blob",
            value_digest=token_digest(tenant_id, "777dup"),
            tpay_status=TpayTokenStatus.ACTIVE,
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_scalar(existing)])

        token = await SubscriptionService(db).save_blik_alias_from_notification(tenant_id, alias_value="777dup")
        assert token.id == existing.id
        db.add.assert_not_called()
