"""PaymentProvider — abstrakcja dostawcy płatności (Story 7.4 + 7.2).

tpay jest jedynym providerem (decyzja 2026-08-28), ale interfejs zostaje
jako furtka pod ekspansję UE (np. Stripe) — dodanie dostawcy ma być
story, nie przebudową (plan-integracji-tpay.md §1 D1).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CheckoutResult:
    """Wynik inicjacji checkoutu (AC1)."""

    transaction_id: str
    transaction_payment_url: str


@dataclass(frozen=True)
class ProviderTransaction:
    """Stan transakcji u dostawcy — reconciliation fallback (AC7)."""

    transaction_id: str
    status: str  # surowy status dostawcy: "paid" | "pending" | "charged_back" | ...
    amount: Decimal
    paid_amount: Decimal | None
    test_mode: bool


@dataclass(frozen=True)
class TokenRegistrationResult:
    """Wynik rejestracji tokena bez obciążenia — Story 7.2 AC2."""

    transaction_payment_url: str  # URL przekierowania płatnika na panel tpay


@dataclass(frozen=True)
class ProviderTokenStatus:
    """Status tokena u dostawcy + wizerunek karty — Story 7.2 AC3."""

    status: str  # ACTIVE | SUSPENDED | DELETED
    card_tail: str | None = None
    card_brand: str | None = None
    expires_at: date | None = None


class PaymentProvider(ABC):
    """Kontrakt dostawcy płatności — implementuje TpayProvider (7.4+)."""

    name: str = "abstract"

    @abstractmethod
    async def create_checkout(
        self,
        *,
        amount: Decimal,
        currency: str,
        description: str,
        order_id: str,
        payer_email: str,
        payer_name: str | None = None,
        group_id: str | None = None,
    ) -> CheckoutResult:
        """Utworzenie transakcji redirect (Panel Transakcyjny) — AC1/AC2."""

    @abstractmethod
    async def charge_recurring(self, **kwargs):  # pragma: no cover — Story 7.2
        """Obciążenie cykliczne (token/alias) — implementuje Story 7.2."""

    @abstractmethod
    async def refund(self, **kwargs):  # pragma: no cover — Story 7.3/7.5
        """Zwrot — implementuje Story 7.3/7.5."""

    @abstractmethod
    async def get_transaction(self, transaction_id: str) -> ProviderTransaction:
        """Odczyt stanu transakcji — wyłącznie fallback/reconciliation (AC7)."""

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: dict) -> bool:
        """Weryfikacja podpisu notyfikacji (JWS + md5sum u tpay) — AC3."""

    # --- Story 7.2: operacje tokenów (Task 2.2) ---

    @abstractmethod
    async def register_card_token(
        self,
        *,
        callback_url: str,
        cli_auth: str | None = None,
    ) -> TokenRegistrationResult:
        """Rejestracja tokena karty bez obciążenia (POST /tokens) — AC2."""

    @abstractmethod
    async def get_token_status(self, token_value: str) -> ProviderTokenStatus:
        """Status tokena + wizerunek karty (GET /tokens/{value}) — AC3."""

    @abstractmethod
    async def delete_token(self, token_value: str) -> None:
        """Usunięcie tokena u dostawcy (DELETE /tokens/{value}) — AC3."""
