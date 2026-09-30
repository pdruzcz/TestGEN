"""tpay /tokens — tokenizacja kart (Story 7.2, AC2/AC3; plan §3.4).

Rejestracja bez obciążenia (``POST /tokens`` → URL przekierowania na panel
tpay), odczyt statusu + wizerunku karty (``GET /tokens/{value}``), usunięcie
(``DELETE /tokens/{value}``). ``cliAuth`` to nasz ``registration_id`` —
korelacja notyfikacji JSON ``data.token`` (handler 7.3 → serwis 7.2).
"""

import logging
from datetime import date

from app.services.billing.providers.base import ProviderTokenStatus, TokenRegistrationResult
from app.services.billing.providers.tpay.client import TpayClient

logger = logging.getLogger(__name__)


async def register_token(
    client: TpayClient,
    *,
    callback_url: str,
    cli_auth: str | None = None,
) -> TokenRegistrationResult:
    """POST /tokens — rejestracja karty bez obciążenia (AC2).

    ``callbackUrl`` to strona powrotu płatnika; ``cliAuth`` (nasz
    ``registration_id``) wraca w notyfikacji ``data.token``.
    """
    payload: dict = {"callbackUrl": callback_url}
    if cli_auth:
        payload["cliAuth"] = cli_auth

    data = await client.post("/tokens", json=payload)
    payment_url = data.get("transactionPaymentUrl") or data.get("transactionUrl")
    if not payment_url:
        raise ValueError(f"tpay register_token unexpected response: {str(data)[:300]}")
    return TokenRegistrationResult(transaction_payment_url=str(payment_url))


async def get_token(client: TpayClient, token_value: str) -> ProviderTokenStatus:
    """GET /tokens/{value} — status (ACTIVE|SUSPENDED|DELETED) + wizerunek (AC3)."""
    data = await client.get(f"/tokens/{token_value}")
    expires_raw = data.get("expirationDate")
    expires_at: date | None = None
    if expires_raw:
        try:
            expires_at = date.fromisoformat(str(expires_raw)[:10])
        except ValueError:
            logger.warning("tpay get_token: nieparsowalny expirationDate %r", expires_raw)
    return ProviderTokenStatus(
        status=str(data.get("status", "unknown")),
        # tpay zwraca wizerunek jako cardVendor/cardTail (spójnie z webhookiem
        # card_brand); tolerancyjnie cardBrand dla starszych odpowiedzi.
        card_tail=(data.get("cardTail") or data.get("tail")),
        card_brand=(data.get("cardVendor") or data.get("cardBrand")),
        expires_at=expires_at,
    )


async def delete_token(client: TpayClient, token_value: str) -> None:
    """DELETE /tokens/{value} — usunięcie tokena u tpay (AC3; lokalny soft
    delete robi SubscriptionService.delete_payment_method)."""
    await client.delete(f"/tokens/{token_value}")
