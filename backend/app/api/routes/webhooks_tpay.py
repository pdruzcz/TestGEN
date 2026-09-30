"""Webhook tpay — Stories 7.4 (AC3/AC4) + 7.3 (AC2/AC5, semantyka odpowiedzi).

POST /api/v1/billing/webhooks/tpay

- ``application/x-www-form-urlencoded`` (transakcje, aliasy BLIK) albo JSON
  (tokenizacja) — klasyfikacja w ``WebhookProcessor`` (7.3 AC2),
- brak JWT — zabezpieczeniem jest podpis JWS (+ md5sum dla transakcji),
- semantyka odpowiedzi (7.3 AC5):
  * sukces/pomijanie (idempotencja, nieobsługiwany typ, brak dopasowania)
    → **HTTP 200** — body ``TRUE`` (form) albo ``{"result": true}`` (JSON)
    — przerywa serię ponowień tpay,
  * błąd walidacji (JWS/md5/śmieciowy payload) → **HTTP 400** — bez ponowień,
  * wyjątek przetwarzania (np. baza niedostępna) → **HTTP 5xx** — tpay
    ponawia wg harmonogramu (1-10 co 1 min, 11-20 co 3 min, ... do 37. próby),
    a idempotencja ``event_uid`` chroni przed podwójnym przetworzeniem,
- każde żądanie (także odrzucone) jest audytowane w ``webhook_events``
  (zapis/commit także przy 400/500 — walidacja i audyt w WebhookProcessor).
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_payment_provider, require_role
from app.models.user import User
from app.services.billing.providers.tpay import TpayProvider
from app.services.billing.webhook_metrics import snapshot as metrics_snapshot
from app.services.billing.webhook_processor import WebhookProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing/webhooks", tags=["billing", "webhooks"])


@router.get(
    "/health",
    summary="Health webhooków płatności (panel admina)",
    description=(
        "**Story 7.3 (AC6, Task 4.3).** Liczniki przetworzonych/odrzuconych/"
        "pominiętych notyfikacji, wiek ostatniego sukcesu i seria kolejnych "
        "porażek (flaga ``alert`` przy >3 — reguła Prometheusa w README modułu). "
        "Wymaga roli **admin**."
    ),
)
async def webhook_health(
    current_user: User = Depends(require_role("admin")),
) -> dict:
    return metrics_snapshot()


def _is_json_request(request: Request, raw_body: bytes) -> bool:
    """Odpowiedź dla notyfikacji JSON — tpay oczekuje ``{"result": true}``."""
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        return True
    return raw_body.lstrip().startswith(b"{")


@router.post(
    "/tpay",
    summary="Webhook tpay (publiczny, JWS + md5sum; wszystkie typy notyfikacji)",
    description=(
        "**Story 7.4 (AC3/AC4) + 7.3 (AC2/AC5).** Macierz typów notyfikacji: "
        "transakcja (``application/x-www-form-urlencoded`` z `tr_id`, `tr_crc`, "
        "`tr_status`), aliasy BLIK (`event=ALIAS_*` + `msg_value[value]`), "
        "tokenizacja JSON (`data.token`). Autoryzacja: podpis JWS "
        "(`X-JWS-Signature`) + `md5sum` (transakcje) — bez JWT. "
        "Sukces/pomijanie → **HTTP 200** (`TRUE` / `{'result': true}`); "
        "błąd walidacji → 400 (bez ponowień); wyjątek przetwarzania → 5xx "
        "(tpay ponawia do 37 prób, idempotencja `event_uid`)."
    ),
)
async def tpay_transaction_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider: TpayProvider = Depends(get_payment_provider),
) -> Response:
    # Surowe body — podpisane przez JWS i klasyfikowane w procesorze (AC2/AC3).
    raw_body = await request.body()
    jws_signature = request.headers.get("X-JWS-Signature")
    is_json = _is_json_request(request, raw_body)

    try:
        processor = WebhookProcessor(db, provider)
        ok, _status = await processor.handle_tpay_notification(raw_body, jws_signature)
        # Audyt (w tym odrzucenia) musi zostać utrwalony również przy 400.
        await db.commit()
    except Exception:
        # AC5: błąd przetwarzania → 5xx, tpay ponawia wg harmonogramu.
        logger.exception("tpay webhook: przetwarzanie nie powiodło się — odpowiadam 5xx (tpay ponowi)")
        try:
            await db.commit()  # best-effort audyt error (samo złapanie w processorze)
        except Exception:
            logger.exception("tpay webhook: commit audytu error niemożliwy")
        return Response(status_code=500, content="FALSE", media_type="text/plain")

    if not ok:
        # Błąd walidacji — 400 bez ponawiania (AC1/AC5).
        return Response(status_code=400, content="FALSE", media_type="text/plain")
    if is_json:
        # Notyfikacje JSON: tpay oczekuje {"result: true} przy HTTP 200.
        return Response(status_code=200, content='{"result":true}', media_type="application/json")
    return Response(status_code=200, content="TRUE", media_type="text/plain")
