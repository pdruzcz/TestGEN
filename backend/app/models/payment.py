"""Modele płatności — Story 7.4 + 7.2.

``PaymentTransaction`` — lokalne lustro transakcji u dostawcy (tpay):
``hidden_description`` (= ``order_id``) to **jedyna** poprawna korelacja
webhook↔zamówienie (``tr_crc``); ``transaction_id`` przechowujemy
długoterminowo (wymóg BOK tpay).

``PaymentToken`` (7.2) — zapisana metoda płatności: token karty (z webhooka
transakcyjnego przy ``save = 1`` albo rejestracji ``POST /tokens``) lub alias
BLIK (PAYID). Wartość tokena jest **szyfrowana AES-256-GCM per-tenant**
(wzorzec 1.54) — do wyszukiwania po wartości służy deterministyczny
``value_digest`` (GCM ma losowy nonce, blob nie jest porównywalny).

``WebhookEvent`` — audyt + idempotencja każdej notyfikacji (także
odrzuconej): ``event_uid`` = ``{tr_id}:{tr_status}`` (tpay gwarantuje ten
sam identyfikator w ponowieniach).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CHARGED_BACK = "charged_back"
    REFUNDED = "refunded"


class WebhookProcessingStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    REJECTED_SIGNATURE = "rejected_signature"
    REJECTED_MD5 = "rejected_md5"
    # 7.3 AC5: zwalidowany podpis, ale śmieciowy payload znanego typu (400 bez ponowień).
    REJECTED_PAYLOAD = "rejected_payload"
    NO_MATCH = "no_match"  # zwalidowana notyfikacja bez lokalnego zamówienia
    # 7.3 AC2: nieobsługiwany typ notyfikacji / brak dopasowania aliasu — TRUE bez błędu.
    SKIPPED = "skipped"
    ERROR = "error"


class TokenKind(StrEnum):
    """Rodzaj zapisanej metody płatności (plan §3.4: token karty / alias BLIK)."""

    CARD_TOKEN = "card_token"
    BLIK_ALIAS_UID = "blik_alias_uid"
    BLIK_ALIAS_PAYID = "blik_alias_payid"


class TpayTokenStatus(StrEnum):
    """Status tokena u tpay + stan lokalnej rejestracji.

    PENDING — rejestracja ``POST /tokens`` rozpoczęta, czekamy na notyfikację
    JSON ``data.token`` (AC2); ACTIVE|SUSPENDED|DELETED — statusy z
    ``GET /tokens/{value}`` (AC3). DELETED to soft delete lokalny.
    """

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class PaymentTransaction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payment_transactions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(20), default="tpay")
    # Identyfikator transakcji u dostawcy (np. ta_bKvkJX9Knk9Ol4od) — BOK tpay.
    # Nullable: rekord tworzony przed odpowiedzią tpay (flush), uzupełniany po niej.
    transaction_id: Mapped[str | None] = mapped_column(String(100), index=True, default=None)
    # tr_id z notyfikacji (title transakcji w tpay) — po opłaceniu.
    title: Mapped[str | None] = mapped_column(String(100), default=None)
    # order_id (UUID) — korelacja z tr_crc webhooka; unique.
    hidden_description: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PaymentStatus.PENDING,
    )
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    test_mode: Mapped[bool] = mapped_column(default=False)
    # Uwaga: atrybut ``meta`` → kolumna ``metadata`` (nazwa atrybutu
    # ``metadata`` koliduje z DeclarativeBase.metadata). M.in. ``plan``
    # zakupiony w checkoutcie — czytany przy aktywacji po webhooku.
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    def __repr__(self) -> str:
        try:
            return (
                f"<PaymentTransaction id={self.id} provider={self.provider} "
                f"status={self.status.value} amount={self.amount}>"
            )
        except Exception:
            return "<PaymentTransaction (detached)>"


class PaymentToken(Base, UUIDMixin, TimestampMixin):
    """Zapisana metoda płatności tenanta — Story 7.2 (AC1/AC2/AC4).

    ``value_encrypted`` — token/alias AES-256-GCM per-tenant (wzorzec 1.54);
    puste dopóki rejestracja (PENDING) nie zakończy się notyfikacją.
    ``value_digest`` — SHA-256(tenant_id:wartość): deterministyczny klucz
    wyszukiwania/idempotencji (nonce GCM losowy → blob nieporównywalny).
    ``registration_id`` — ``cliAuth`` korelacji notyfikacji ``data.token``
    z rejestracją ``POST /tokens`` (AC2).
    """

    __tablename__ = "payment_tokens"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[TokenKind] = mapped_column(
        Enum(
            TokenKind,
            name="payment_token_kind",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
    )
    value_encrypted: Mapped[bytes] = mapped_column(LargeBinary, default=b"")
    value_digest: Mapped[str] = mapped_column(String(64), default="", index=True)
    card_tail: Mapped[str | None] = mapped_column(String(4), default=None)
    card_brand: Mapped[str | None] = mapped_column(String(20), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    tpay_status: Mapped[TpayTokenStatus] = mapped_column(
        Enum(
            TpayTokenStatus,
            name="tpay_token_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=TpayTokenStatus.PENDING,
    )
    is_default: Mapped[bool] = mapped_column(default=False)
    registration_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, default=None)

    def __repr__(self) -> str:
        try:
            return (
                f"<PaymentToken id={self.id} kind={self.kind.value} "
                f"status={self.tpay_status.value} tenant={self.tenant_id}>"
            )
        except Exception:
            return "<PaymentToken (detached)>"


class WebhookEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "webhook_events"

    # Idempotencja (AC4): ten sam tr_id + tr_status w ponowieniach → pomijane.
    event_uid: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(20), default="tpay")
    type: Mapped[str] = mapped_column(String(50), default="transaction")
    raw: Mapped[dict] = mapped_column(JSONB)
    processing_status: Mapped[str] = mapped_column(String(30))
    # 7.3 AC4/AC5: przyczyna odrzucenia/błędu przy audycie (stack trace w logach).
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    def __repr__(self) -> str:
        try:
            return f"<WebhookEvent uid={self.event_uid} status={self.processing_status}>"
        except Exception:
            return "<WebhookEvent (detached)>"
