"""Testy integracyjne sandbox tpay — Story 7.4 (Task 8.4, marker `billing`).

BIEGNĄ TYLKO z env: ``TPAY_CLIENT_ID``/``TPAY_CLIENT_SECRET``/``TPAY_SECURITY_CODE``/
``TPAY_MERCHANT_ID`` ustawione ORAZ ``TPAY_SANDBOX_E2E=1`` (opt-in):

    TPAY_SANDBOX_E2E=1 python -m pytest tests/integration/test_tpay_sandbox.py -m billing

Kwoty sterujące scenariuszami biorą się ze stałych fixtures (§2.1/§3.2a) —
NIE z cen planów. Pełny przepływ „karta testowa → webhook → aktywacja"
wymaga ręcznego opłacenia na Panelu Transakcyjnym — tutaj weryfikujemy
ścieżkę API: OAuth → create transaction → get transaction (status pending).
"""

import os

import pytest

pytestmark = [
    pytest.mark.billing,
    pytest.mark.tpay_sandbox,  # Story 7.12: profil integracyjny z prawdziwym sandboxem
    pytest.mark.skipif(
        os.getenv("TPAY_SANDBOX_E2E") != "1",
        reason="sandbox integration opt-in: ustaw TPAY_SANDBOX_E2E=1 + sekrety TPAY_* (Story 7.4 §2.1)",
    ),
]

from app.core.config_billing import get_billing_settings  # noqa: E402
from app.services.billing.providers.tpay import TpayProvider  # noqa: E402
from tests.fixtures.tpay_fixtures import TPAY_SANDBOX_CHECKOUT_AMOUNT  # noqa: E402


async def test_sandbox_oauth_and_create_transaction():
    """F0 smoke: token OAuth + transakcja redirect w sandboxie (bez opłacania)."""
    settings = get_billing_settings()
    assert settings.is_sandbox, "test wymaga TPAY_ENV=sandbox"
    assert settings.tpay_client_id, "brak TPAY_CLIENT_ID w env"

    provider = TpayProvider(settings)
    checkout = await provider.create_checkout(
        amount=TPAY_SANDBOX_CHECKOUT_AMOUNT,  # kwota testowa z fixtures, nie cena planu
        currency="PLN",
        description="TestGEN — smoke test integracyjny (7.4)",
        order_id=f"smoke-{os.urandom(4).hex()}",
        payer_email="testgen@nexio.pl",
    )
    assert checkout.transaction_id.startswith("ta_")
    assert "tpay.com" in checkout.transaction_payment_url

    # Reconciliation fallback (AC7) — jednorazowy odczyt świeżo utworzonej transakcji.
    remote = await provider.get_transaction(checkout.transaction_id)
    assert remote.transaction_id == checkout.transaction_id
    assert remote.status == "pending"  # nieopłacona


class TestSandboxTokensAndRecurring:
    """Story 7.2 (Task 8.5) — tokenizacja + rejestracja aliasu PAYID + refuseNoPayId.

    Pełny przepływ „karta z save=1 → odnowienie tokenem" wymaga ręcznego
    opłacenia na Panelu (jak w 7.4); tutaj ścieżki automatyczne: rejestracja
    ``POST /tokens`` (URL panelu), checkout z ``blikPaymentData.aliases`` na
    kwocie PAYID (x.08) oraz odmowa banku bez Płatności Powtarzalnych.
    """

    async def test_register_token_returns_panel_url(self):
        """AC2 — rejestracja karty bez obciążenia: URL przekierowania."""
        provider = TpayProvider(get_billing_settings())
        registration = await provider.register_card_token(
            callback_url="https://testgen.nexio.pl/billing/payment-methods/return",
            cli_auth=f"reg-{os.urandom(4).hex()}",
        )
        assert registration.transaction_payment_url.startswith("http")
        assert "tpay.com" in registration.transaction_payment_url

    async def test_checkout_with_blik_alias_on_payid_amount(self):
        """AC4 — checkout z rejestracją aliasu PAYID (kwota x.08 z fixtures)."""
        from decimal import Decimal

        from tests.fixtures.tpay_fixtures import TPAY_SANDBOX_CHECKOUT_AMOUNT

        provider = TpayProvider(get_billing_settings())
        checkout = await provider.create_checkout(
            amount=Decimal(TPAY_SANDBOX_CHECKOUT_AMOUNT) + Decimal("0.08"),
            currency="PLN",
            description="TestGEN — rejestracja PAYID (7.2)",
            order_id=f"payid-{os.urandom(4).hex()}",
            payer_email="testgen@nexio.pl",
        )
        assert checkout.transaction_id.startswith("ta_")

    async def test_bank_without_repeatable_payments_refuses_payid(self):
        """AC7 — kwota 495.00 + opis mock → refuseNoPayId (fallback: karta)."""
        from decimal import Decimal

        import pytest as _pytest

        from app.services.billing.providers.tpay.client import TpayApiError
        from tests.fixtures.tpay_fixtures import TPAY_BANK_NO_REPEATABLE_AMOUNT

        provider = TpayProvider(get_billing_settings())
        with _pytest.raises(TpayApiError) as excinfo:
            await provider.create_checkout(
                amount=Decimal(TPAY_BANK_NO_REPEATABLE_AMOUNT),
                currency="PLN",
                description="mock",
                order_id=f"refuse-{os.urandom(4).hex()}",
                payer_email="testgen@nexio.pl",
            )
        assert "refusenopayid" in str(excinfo.value).lower()


class TestSandboxNotificationAcceptance:
    """Story 7.3 (Task 6.5) — odbiór realnej notyfikacji przez testgen.nexio.pl.

    Narzędzie testowania powiadomień z Panelu tpay (§2.1 pkt 6 planu):
    Panel → Transakcje → wyślij testowe powiadomienie. Ten test weryfikuje
    GOTOWOŚĆ konfiguracji (URL notyfikacji + sekrety do md5sum) i dokumentuje
    procedurę ręczną — samo kliknięcie w Panelu jest poza automatem:

    1. Panel tpay (sandbox) → Ustawienia → Powiadomienia → URL:
       ``https://testgen.nexio.pl/api/v1/billing/webhooks/tpay`` + „Zezwól
       na nadpisanie adresu URL powiadomienia" (wymagane dla aliasów BLIK).
    2. Panel → narzędzie testu powiadomień → wyślij testową notyfikację.
    3. Weryfikacja odbioru (na serwerze):
       ``SELECT event_uid, processing_status, error_message FROM webhook_events
       ORDER BY created_at DESC LIMIT 5;`` — świeży wiersz + ``GET
       /api/v1/billing/webhooks/health`` (licznik processed rośnie).
    """

    async def test_notification_config_ready(self):
        """URL notyfikacji wskazuje na publiczną domenę; sekrety obecne."""
        settings = get_billing_settings()
        assert settings.tpay_notification_url.startswith("https://testgen.nexio.pl")
        assert settings.tpay_client_id, "brak TPAY_CLIENT_ID w env"
        assert settings.tpay_security_code.get_secret_value(), "brak TPAY_SECURITY_CODE w env"

    async def test_md5sum_formula_matches_sandbox_secrets(self):
        """Wzór md5 z REALNYMI sekretami sandbox — sanity przed testem Panelu."""
        from tests.fixtures.tpay_fixtures import compute_md5sum

        settings = get_billing_settings()
        md5 = compute_md5sum(
            settings.tpay_merchant_id,
            "TR-SANDBOX-TEST",
            "30.00",
            "ord-sandbox-test",
            settings.tpay_security_code.get_secret_value(),
        )
        assert len(md5) == 32  # heksadecimalny md5

        # Lokalna weryfikacja reciprokalna walidatorem produkcyjnym.
        from app.services.billing.providers.tpay.webhooks import TpayWebhookVerifier

        verifier = TpayWebhookVerifier(settings)
        assert verifier.compute_md5sum(tr_id="TR-SANDBOX-TEST", tr_amount="30.00", tr_crc="ord-sandbox-test") == md5
