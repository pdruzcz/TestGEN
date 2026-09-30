"""Billing schemas — Story 7.1 (plany, subskrypcje, użycie) + 7.4 (checkout, status)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentStatus
from app.models.plan_change import PlanChangeStatus, PlanChangeType
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: PlanName
    display_name: str
    price_monthly: Decimal
    currency: str
    features: dict
    is_active: bool
    sort_order: int


class PlanComparisonOut(BaseModel):
    """Odpowiedź GET /billing/plans — z aktualnym planem tenanta i linkami prawnymi (wymóg tpay)."""

    plans: list[PlanOut]
    current_plan: PlanName | None = None
    terms_url: str
    privacy_policy_url: str


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_id: uuid.UUID
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    next_charge_at: datetime | None = None
    cancel_at_period_end: bool
    trial_end: datetime | None = None


class UsageEntryOut(BaseModel):
    """Story 7.8 (Task 4): zużycie zasobu z limitem planu i procentem wykorzystania."""

    used: int
    limit: int | None = None  # None = unlimited
    percent: float | None = None  # None = unlimited


# --- Story 7.9: dashboard zużycia zasobów (AC5) ---


class PeriodOut(BaseModel):
    """Okres rozliczeniowy dashboardu (AC2)."""

    start: datetime
    end: datetime


class UsageCounterOut(BaseModel):
    """Karta zasobu na dashboardzie (AC1); ``limit``/``percentage`` None = unlimited."""

    type: Literal["analyses", "test_cases", "storage_bytes", "files_per_analysis"]
    value: int
    limit: int | None = None
    percentage: float | None = None


class ForecastOut(BaseModel):
    """Prognoza osiągnięcia limitu analiz (AC4) — opcjonalna część dashboardu."""

    counter_type: Literal["analyses", "test_cases", "storage_bytes", "files_per_analysis"]
    limit_date: date
    avg_daily: float
    days_to_limit: int
    exceeds_before_period_end: bool


class UsageDashboardOut(BaseModel):
    """GET /billing/usage/dashboard (AC5) — pełne dane dashboardu zużycia."""

    current_period: PeriodOut
    plan: str | None = None
    counters: list[UsageCounterOut]
    forecast: ForecastOut | None = None
    days_remaining: int


class UsageHistoryPointOut(BaseModel):
    """Punkt wykresu historii (AC3) — skumulowane zużycie na dzień."""

    date: date
    value: int


class UsageHistoryOut(BaseModel):
    """GET /billing/usage/history (AC3) — daily snapshoty do wykresu liniowego."""

    counter_type: Literal["analyses", "test_cases", "storage_bytes", "files_per_analysis"]
    days: int
    points: list[UsageHistoryPointOut]


class SubscriptionStatusOut(BaseModel):
    """Zbiorczy status subskrypcji tenanta (plan + limity)."""

    plan: PlanName
    status: SubscriptionStatus
    limits: dict


# --- Story 7.13: widoczne-zablokowane moduły gated (FR71) ---


class ModuleLockOut(BaseModel):
    """Status pojedynczego modułu: ``required_plan`` tylko gdy zablokowany."""

    key: str
    locked: bool
    required_plan: PlanName | None = None


class FeaturesStatusOut(BaseModel):
    """GET /billing/features — plan tenanta + mapa zablokowanych modułów (FE)."""

    current_plan: PlanName
    modules: list[ModuleLockOut]


# --- Story 7.4: checkout redirect (AC1) + status transakcji (AC2/AC7) ---


class CheckoutIn(BaseModel):
    """POST /billing/checkout — jedyny cykl: miesięczny (bez pola rocznego, CR#2)."""

    plan: Literal["basic", "premium"]


class CheckoutOut(BaseModel):
    """Odpowiedź checkoutu — FE przekierowuje płatnika na `transaction_payment_url`."""

    order_id: str
    transaction_id: str
    transaction_payment_url: str
    plan: Literal["basic", "premium"]
    amount: Decimal
    currency: str


class TransactionStatusOut(BaseModel):
    """GET /billing/transactions/{order_id} — status lokalny (polling stron powrotu)."""

    order_id: str
    status: PaymentStatus
    plan: PlanName | None = None
    amount: Decimal
    currency: str
    test_mode: bool = False


# --- Story 7.2: metody płatności (tokeny kart / aliasy BLIK) ---


class PaymentMethodOut(BaseModel):
    """GET /billing/payment-methods — pozycja listy (AC3): rodzaj, wizerunek, status."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["card_token", "blik_alias_uid", "blik_alias_payid"]
    card_tail: str | None = None
    card_brand: str | None = None
    tpay_status: Literal["pending", "active", "suspended", "deleted"]
    is_default: bool
    created_at: datetime


class PaymentMethodRegistrationOut(BaseModel):
    """POST /billing/payment-methods — URL przekierowania na rejestrację karty (AC2)."""

    token_id: uuid.UUID
    registration_url: str


# --- Story 7.5: upgrade/downgrade planu z prorated billing ---


class PlanChangeIn(BaseModel):
    """POST /billing/subscription/change — plan docelowy (freemium = downgrade)."""

    plan: PlanName


class ProrationOut(BaseModel):
    """GET /billing/subscription/proration — lokalny podgląd proration (AC5)."""

    amount: Decimal
    period_days: int
    remaining_days: int
    current_plan: PlanName
    new_plan: PlanName
    current_price: Decimal
    new_price: Decimal
    full_price: Decimal
    change_type: Literal["upgrade", "downgrade"]
    currency: str
    next_charge_at: datetime | None = None


class PlanChangeOut(BaseModel):
    """Rekord historii zmiany planu (AC4)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_plan: PlanName
    to_plan: PlanName
    change_type: PlanChangeType
    status: PlanChangeStatus
    requested_at: datetime
    effective_at: datetime | None = None
    proration_details: dict


class PlanChangeResultOut(BaseModel):
    """Odpowiedź POST /billing/subscription/change (AC1/AC2)."""

    change: PlanChangeOut
    change_type: PlanChangeType
    amount: Decimal
    currency: str
    payment_required: bool
    payment_url: str | None = None
    order_id: str | None = None


# --- Story 7.6: faktury VAT ---


class InvoiceOut(BaseModel):
    """GET /billing/invoices — pozycja listy (AC5): numer, data, kwota, status."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    issue_date: date
    sale_date: date
    buyer_name: str
    subtotal_net: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_gross: Decimal
    currency: str
    payment_method: Literal["card", "bank_transfer", "blik"]
    status: Literal["issued", "canceled", "corrected"]
    pdf_available: bool
    created_at: datetime


class InvoiceListOut(BaseModel):
    """GET /billing/invoices — strona listy (AC5), malejąco po dacie, 20/stronę."""

    items: list[InvoiceOut]
    total: int
    page: int
    size: int


# --- Story 7.7: portal billingowy (metody płatności, historia, anulowanie) ---


class SubscriptionPaymentMethodOut(BaseModel):
    """Aktywna metoda płatności subskrypcji w detailu (AC3)."""

    model_config = ConfigDict(from_attributes=True)

    kind: Literal["card_token", "blik_alias_uid", "blik_alias_payid"]
    card_tail: str | None = None
    card_brand: str | None = None
    tpay_status: Literal["pending", "active", "suspended", "deleted"]
    is_default: bool


class SubscriptionDetailOut(SubscriptionOut):
    """GET /billing/subscription (AC3) — rozbudowany detail portalu.

    Nadzbiór ``SubscriptionOut`` (kompatybilny wstecz): plan, metoda płatności,
    zaplanowany downgrade (7.5), stan windykacji (``grace_until``).
    """

    plan_name: PlanName | None = None
    plan_display_name: str | None = None
    plan_price_monthly: Decimal | None = None
    plan_currency: str | None = None
    payment_method: SubscriptionPaymentMethodOut | None = None
    pending_change: PlanChangeOut | None = None
    grace_until: datetime | None = None


class TransactionOut(BaseModel):
    """GET /billing/transactions — pozycja historii (AC2)."""

    id: uuid.UUID
    created_at: datetime
    amount: Decimal
    currency: str
    status: PaymentStatus
    paid_amount: Decimal | None = None
    method: Literal["card", "blik", "bank_transfer"] | None = None
    transaction_id: str | None = None  # identyfikator u tpay (BOK)
    order_id: str | None = None  # hidden_description — korelacja webhooka
    invoice_id: uuid.UUID | None = None
    invoice_number: str | None = None
    test_mode: bool = False


class TransactionListOut(BaseModel):
    """GET /billing/transactions — strona listy (AC2), malejąco po dacie."""

    items: list[TransactionOut]
    total: int
    page: int
    size: int


class InvoiceDataOut(BaseModel):
    """GET/PUT /billing/invoice-data — dane fakturowe tenanta (AC4)."""

    model_config = ConfigDict(from_attributes=True)

    company_name: str
    nip: str | None = None
    address: dict


class InvoiceDataIn(BaseModel):
    """PUT /billing/invoice-data (AC4): nazwa firmy fakturowa, NIP, adres."""

    company_name: str = Field(min_length=1, max_length=255)
    nip: str | None = Field(default=None, max_length=20)
    street: str = Field(default="", max_length=255)
    city: str = Field(default="", max_length=100)
    postal_code: str = Field(default="", max_length=20)
    country: str = Field(default="Polska", max_length=100)
