"""Billing configuration — Story 7.1 (§3.2a) + Story 7.4 (§3.2, plan-integracji-tpay.md).

Ceny planów i URL-e dokumentów prawnych pochodzą z env — wymiana cen =
zmiana env + re-seed, bez deployu kodu. Sandbox tpay: kwoty testowe
sterujące scenariuszami płatności; produkcja: 30/50 PLN.

Sekrety tpay (``TPAY_CLIENT_SECRET``, ``TPAY_SECURITY_CODE``) wyłącznie
z env/secrets — nigdy w kodzie ani repo (wymóg tpay; rotacja +
monitorowanie użycia).
"""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_TPAY_BASE_URL_SANDBOX = "https://openapi.sandbox.tpay.com"
_TPAY_BASE_URL_PRODUCTION = "https://api.tpay.com"


class BillingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ceny miesięczne (jedyny cykl — bez rocznych, decyzja 2026-08-28)
    billing_basic_monthly_price: Decimal = Decimal("30.00")
    billing_premium_monthly_price: Decimal = Decimal("50.00")
    billing_currency: str = "PLN"

    # Dokumenty prawne — tpay wymaga osadzenia regulaminu i polityki
    # prywatności na stronach związanych z zakupami (linki z configu,
    # nigdy hardcode w komponencie).
    billing_terms_url: str = "https://test-gen.pl/regulamin/"
    billing_privacy_policy_url: str = "https://test-gen.pl/polityka/"

    # --- Rate limiting (Story 7.8, AC2) — fallback awaryjny, gdy cache
    # z ``features.rate_limit_per_min`` pusty (jedno źródło prawdy: DB).
    # RATE_LIMIT_BASIC: Freemium/Basic; RATE_LIMIT_PROFESSIONAL: Premium.
    rate_limit_enabled: bool = True
    rate_limit_basic: int = 100
    rate_limit_professional: int = 1000

    # --- tpay Open API (Story 7.4, §3.2 plan-integracji-tpay.md) ---

    tpay_env: Literal["sandbox", "production"] = "sandbox"
    # Puste → pochodna od ``tpay_env`` (sandbox/production base URL).
    tpay_base_url: str = ""
    tpay_client_id: str = ""
    tpay_client_secret: SecretStr = SecretStr("")
    # Kod zabezpieczający (Panel → Powiadomienia → Zabezpieczenia) — do md5sum.
    tpay_security_code: SecretStr = SecretStr("")
    # Numer akceptanta (login panelu) — pierwszy składnik wzoru md5sum.
    tpay_merchant_id: str = ""
    tpay_notification_url: str = "https://testgen.nexio.pl/api/v1/billing/webhooks/tpay"
    # Strony powrotu płatnika (Angular, Story 7.4 — Task 6).
    tpay_success_url: str = "https://testgen.nexio.pl/billing/checkout/success"
    tpay_error_url: str = "https://testgen.nexio.pl/billing/checkout/error"
    # Powrót z rejestracji karty bez obciążenia (callbackUrl POST /tokens — 7.2 AC2).
    tpay_payment_methods_return_url: str = "https://testgen.nexio.pl/billing/payment-methods/return"
    # Grupy płatności Panelu Transakcyjnego (§3.2): 150 = BLIK, 103 = karta.
    tpay_group_id_blik: str = "150"
    tpay_group_id_card: str = "103"
    # Ograniczenia aliasu BLIK Płatności Powtarzalne (PAYID, model A — 7.2 AC4):
    # limit pojedynczy = cena planu, limit całkowity = cena x liczba płatności.
    tpay_blik_alias_frequency: str = "eachMonth"
    tpay_blik_alias_total_limit_payments: int = 12
    tpay_blik_alias_expiration_days: int = 730
    # Certyfikat x509 do weryfikacji JWS notyfikacji (AC3) — pobierany i cache'owany.
    tpay_jws_cert_url: str = "https://secure.tpay.com/x509/notifications-jws.pem"

    # --- Faktury VAT (Story 7.6, AC1) — dane sprzedawcy (TestGEN) z env ---
    # Snapshot do każdego rekordu Invoice w chwili wystawienia; zmiana env
    # nie dotyka już wystawionych faktur (wzorzec AC4). Address jako JSON
    # (pydantic-settings parsuje złożone typy z env): street/city/postal_code/country.
    # Realne dane rejestrowe spółki jako defaulty (2026-09-22) — deploy nie
    # wymaga env; nadpisywalne przez INVOICE_SELLER_* jak dotąd.
    invoice_seller_name: str = "TestGEN Sp. z o.o."
    invoice_seller_nip: str = "7394004057"
    invoice_seller_krs: str = "0001118599"
    invoice_seller_regon: str = "529240482"
    invoice_seller_address: dict[str, str] = Field(
        default_factory=lambda: {
            "street": "ul. Karola Brzostowskiego 10A / 4",
            "city": "Augustów",
            "postal_code": "16-300",
            "country": "Polska",
        }
    )

    @property
    def api_base_url(self) -> str:
        """Bazowy URL Open API — jawny ``TPAY_BASE_URL`` albo pochodna ``TPAY_ENV``."""
        if self.tpay_base_url:
            return self.tpay_base_url.rstrip("/")
        return _TPAY_BASE_URL_PRODUCTION if self.tpay_env == "production" else _TPAY_BASE_URL_SANDBOX

    @property
    def is_sandbox(self) -> bool:
        return self.tpay_env == "sandbox"


@lru_cache
def get_billing_settings() -> BillingSettings:
    return BillingSettings()
