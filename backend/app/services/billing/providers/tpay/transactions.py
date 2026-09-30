"""tpay /transactions — create (AC1) + get (reconciliation fallback, AC7) +
rejestracja aliasu BLIK przy pierwszej płatności (7.2 AC4).

Tworzenie transakcji redirect: kwota, płatnik, ``hiddenDescription``
(= nasz ``order_id`` — jedyna poprawna korelacja webhook↔zamówienie),
callbacki powrotu płatnika i notyfikacji (nadpisanie per-transakcja).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.core.config_billing import BillingSettings
from app.services.billing.providers.base import CheckoutResult, ProviderTransaction
from app.services.billing.providers.tpay.client import TpayClient

# Statusy transakcji w Open API tpay, które uznajemy za opłacone.
_PAID_STATUSES = {"paid"}


def build_blik_alias_registration(
    amount: Decimal, settings: BillingSettings, *, value: str | None = None
) -> dict[str, Any]:
    """Wpis ``blikPaymentData.aliases[0]`` — rejestracja aliasu PAYID (AC4).

    Ograniczenia wg konfiguracji planu: limit pojedynczy = kwota subskrypcji
    (model A — stała kwota bez potwierdzenia w aplikacji), limit całkowity =
    kwota x liczba płatności, horyzont ``expiration_days``. Model O (kwota
    zmienna) poza v1 — wymaga akceptacji tpay (AC7).

    ``value`` (7.3): wartość aliasu generowana przez merchanta — docs tpay
    oczekują, że to my ją dostarczamy (korelacja notyfikacji ``ALIAS_*``
    z tenantem po ``meta.blik_alias_value`` transakcji rejestracji).
    """
    today = datetime.now(UTC).date()
    entry: dict[str, Any] = {
        "frequency": settings.tpay_blik_alias_frequency,
        "singleLimitAmount": float(amount),
        "totalLimitAmount": float(amount * settings.tpay_blik_alias_total_limit_payments),
        "initDate": today.isoformat(),
        "expirationDate": (today + timedelta(days=settings.tpay_blik_alias_expiration_days)).isoformat(),
    }
    if value:
        entry["value"] = value
    return entry


async def create_transaction(
    client: TpayClient,
    settings: BillingSettings,
    *,
    amount: Decimal,
    currency: str,
    description: str,
    payer_email: str,
    payer_name: str | None,
    hidden_description: str,
    success_url: str,
    error_url: str,
    notification_url: str,
    group_id: str | None = None,
    blik_alias: dict[str, Any] | None = None,
) -> CheckoutResult:
    """POST /transactions — transakcja redirect (AC1).

    ``blik_alias`` (wpis z ``build_blik_alias_registration``) dołącza
    ``blikPaymentData.aliases`` + ``autopayment.model = A`` — gdy płatnik
    zapłaci BLIK, alias Płatności Powtarzalnych zarejestruje się przy
    pierwszej płatności (7.2 AC4).
    """
    payload: dict[str, Any] = {
        "amount": float(amount),
        "description": description,
        "hiddenDescription": hidden_description,
        "payer": {"email": payer_email, "name": payer_name or payer_email},
        "callbacks": {
            # camelCase wg Open API tpay (`payerURLs` → 400 not_valid, code 7703c766)
            "payerUrls": {"success": success_url, "error": error_url},
            "notification": {"url": notification_url},
        },
    }
    if group_id:
        payload["pay"] = {"groupId": int(group_id)}
    if blik_alias is not None:
        payload["blikPaymentData"] = {"aliases": [blik_alias]}
        payload["autopayment"] = {"model": "A"}

    data = await client.post("/transactions", json=payload)
    transaction_id = data.get("transactionId")
    payment_url = data.get("transactionPaymentUrl")
    if not transaction_id or not payment_url:
        raise ValueError(f"tpay create_transaction unexpected response: {str(data)[:300]}")
    return CheckoutResult(transaction_id=str(transaction_id), transaction_payment_url=str(payment_url))


async def create_recurring_transaction(
    client: TpayClient,
    settings: BillingSettings,
    *,
    amount: Decimal,
    currency: str,
    description: str,
    payer_email: str,
    hidden_description: str,
    notification_url: str,
    card_token: str | None = None,
    blik_alias: str | None = None,
) -> CheckoutResult:
    """POST /transactions — obciążenie cykliczne merchant-initiated (7.2 AC5).

    Karta: ``pay.cardPaymentData.token`` (bez udziału użytkownika); BLIK:
    sam alias (``blikPaymentData.type = 2``). Bez ``payerUrls`` — płatnik
    nie uczestniczy; rezultat przez ten sam webhook transakcyjny co 7.4.
    """
    payload: dict[str, Any] = {
        "amount": float(amount),
        "description": description,
        "hiddenDescription": hidden_description,
        "payer": {"email": payer_email, "name": payer_email},
        "callbacks": {"notification": {"url": notification_url}},
    }
    if card_token:
        payload["pay"] = {"cardPaymentData": {"token": card_token}}
    elif blik_alias:
        payload["blikPaymentData"] = {"type": 2, "aliases": [{"value": blik_alias}]}
    else:
        raise ValueError("create_recurring_transaction wymaga card_token albo blik_alias")

    data = await client.post("/transactions", json=payload)
    transaction_id = data.get("transactionId")
    if not transaction_id:
        raise ValueError(f"tpay create_recurring_transaction unexpected response: {str(data)[:300]}")
    return CheckoutResult(
        transaction_id=str(transaction_id),
        transaction_payment_url=str(data.get("transactionPaymentUrl", "")),
    )


async def get_transaction(client: TpayClient, transaction_id: str) -> ProviderTransaction:
    """GET /transactions/{id} — wyłącznie fallback/reconciliation (AC7).

    Okresowy polling API tpay jest wzbroniony (wymóg tpay) — wywołanie
    tylko zdarzeniowo (np. płatnik wrócił przed webhookiem).
    """
    data = await client.get(f"/transactions/{transaction_id}")
    amount = data.get("amount")
    paid_amount = data.get("paidAmount")
    return ProviderTransaction(
        transaction_id=str(data.get("transactionId", transaction_id)),
        status=str(data.get("status", "unknown")),
        amount=Decimal(str(amount)) if amount is not None else Decimal("0"),
        paid_amount=Decimal(str(paid_amount)) if paid_amount is not None else None,
        test_mode=bool(data.get("testMode", False)),
    )


def is_paid(status: str) -> bool:
    """Czy surowy status tpay oznacza transakcję opłaconą."""
    return status in _PAID_STATUSES
