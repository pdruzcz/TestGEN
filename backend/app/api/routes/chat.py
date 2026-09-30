"""AI Assistant (chatbot) — Story 6.14, Task 8 (FR66, AC2, AC7).

POST /chat/message — strumieniuje odpowiedź asystenta jako Server-Sent Events
(``text/event-stream``). Zużycie tokenów trafia do ``LLMUsage`` z modułem
``chatbot`` (rozliczenie per tenant).
"""

import logging
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user, get_tenant
from app.models.user import User
from app.schemas.chat import ChatMessageRequest
from app.services.chat import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post(
    "/chat/message",
    summary="Zadaj pytanie asystentowi AI (odpowiedź strumieniowana przez SSE)",
    response_class=StreamingResponse,
)
async def post_chat_message(
    payload: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: uuid.UUID = Depends(get_tenant),
) -> StreamingResponse:
    """Zwraca strumień zdarzeń SSE: ``token`` → ... → ``done`` albo ``error``."""
    return StreamingResponse(
        chat_service.stream_chat(request=payload, tenant_id=tenant_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Wyłącza buforowanie w nginx — bez tego tokeny docierają hurtem.
            "X-Accel-Buffering": "no",
        },
    )
