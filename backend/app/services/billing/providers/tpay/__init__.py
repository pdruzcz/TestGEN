"""tpay — jedyny provider płatności (Story 7.4 + 7.2; D1, plan-integracji-tpay.md).

``TpayProvider`` składa klient HTTP (``client``), zasoby /transactions
(``transactions``) i /tokens (``tokens``, 7.2) oraz weryfikator notyfikacji
(``webhooks``) w kontrakt ``PaymentProvider``. ``refund`` wypełnia Stories
7.3/7.5 — interfejs jest stabilny od 7.4.
"""

from decimal import Decimal

from redis.asyncio import Redis

from app.core.config_billing import BillingSettings, get_billing_settings
from app.services.billing.providers.base import (
    CheckoutResult,
    PaymentProvider,
    ProviderTokenStatus,
    ProviderTransaction,
    TokenRegistrationResult,
)
from app.services.billing.providers.tpay import tokens as token_api
from app.services.billing.providers.tpay import transactions as txn_api
from app.services.billing.providers.tpay.client import TpayClient
from app.services.billing.providers.tpay.webhooks import TpayWebhookVerifier


class TpayProvider(PaymentProvider):
    name = "tpay"

    def __init__(
        self,
        settings: BillingSettings | None = None,
        redis: Redis | None = None,
        *,
        transport=None,
        pinned_cert_pem: str | None = None,
    ) -> None:
        self.settings = settings or get_billing_settings()
        self._client = TpayClient(self.settings, redis=redis, transport=transport)
        self._verifier = TpayWebhookVerifier(self.settings, pinned_cert_pem=pinned_cert_pem)

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
        blik_alias_value: str | None = None,
    ) -> CheckoutResult:
        # Rejestracja aliasu BLIK (PAYID, model A) wliczona w każdy checkout —
        # gdy płatnik wybierze BLIK, alias zarejestruje się przy pierwszej
        # płatności (7.2 AC4); płatność kartą pozostaje niezmieniona.
        # ``blik_alias_value`` (7.3): nasza wartość aliasu → notyfikacje
        # ``ALIAS_*`` korelują tenanta po ``meta.blik_alias_value``.
        blik_alias = txn_api.build_blik_alias_registration(amount, self.settings, value=blik_alias_value)
        return await txn_api.create_transaction(
            self._client,
            self.settings,
            amount=amount,
            currency=currency,
            description=description,
            payer_email=payer_email,
            payer_name=payer_name,
            hidden_description=order_id,
            success_url=self.settings.tpay_success_url,
            error_url=self.settings.tpay_error_url,
            notification_url=self.settings.tpay_notification_url,
            group_id=group_id,
            blik_alias=blik_alias,
        )

    async def charge_recurring(
        self,
        *,
        amount: Decimal,
        currency: str,
        description: str,
        order_id: str,
        payer_email: str,
        card_token: str | None = None,
        blik_alias: str | None = None,
    ) -> CheckoutResult:
        """Obciążenie cykliczne (7.2 AC5) — karta ``pay.cardPaymentData.token``
        albo BLIK alias (``blikPaymentData.type = 2``); rezultat przez webhook."""
        return await txn_api.create_recurring_transaction(
            self._client,
            self.settings,
            amount=amount,
            currency=currency,
            description=description,
            payer_email=payer_email,
            hidden_description=order_id,
            notification_url=self.settings.tpay_notification_url,
            card_token=card_token,
            blik_alias=blik_alias,
        )

    async def refund(self, **kwargs):  # pragma: no cover — Story 7.3/7.5
        raise NotImplementedError("refund — Story 7.3/7.5")

    async def get_transaction(self, transaction_id: str) -> ProviderTransaction:
        return await txn_api.get_transaction(self._client, transaction_id)

    # --- Story 7.2: operacje tokenów (Task 2) ---

    async def register_card_token(
        self,
        *,
        callback_url: str,
        cli_auth: str | None = None,
    ) -> TokenRegistrationResult:
        return await token_api.register_token(self._client, callback_url=callback_url, cli_auth=cli_auth)

    async def get_token_status(self, token_value: str) -> ProviderTokenStatus:
        return await token_api.get_token(self._client, token_value)

    async def delete_token(self, token_value: str) -> None:
        await token_api.delete_token(self._client, token_value)

    def verify_webhook(self, raw_body: bytes, headers: dict) -> bool:
        """Sync kontrakt ABC — tpay wymaga async (pobranie certyfikatu),
        dlatego właściwa logika jest w :meth:`verify_webhook_async`
        (wywoływanej przez WebhookProcessor)."""
        raise NotImplementedError("use TpayProvider.verify_webhook_async (async cert fetch)")

    async def verify_webhook_async(self, raw_body: bytes, jws_signature: str | None) -> bool:
        return await self._verifier.verify(raw_body, jws_signature)

    @property
    def verifier(self) -> TpayWebhookVerifier:
        return self._verifier
