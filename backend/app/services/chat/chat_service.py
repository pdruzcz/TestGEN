"""Serwis AI Assistant — Story 6.14, Task 8 (AC2, AC7).

Buduje system prompt (odpowiedzi po polsku, referencje ``@ref:{type}:{id}``)
i zamienia strumień tokenów z LLM Gateway na zdarzenia SSE:

- ``token`` — kolejny fragment odpowiedzi (``{"content": "..."}``),
- ``done``  — koniec odpowiedzi (``{"conversationId": ..., "content": ...}``),
- ``error`` — błąd (``{"code": ..., "message": ...}``), komunikat po polsku.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator

from app.schemas.chat import ChatContext, ChatMessageRequest
from app.services.analysis.llm_gateway import (
    LLMError,
    LLMMessage,
    LLMProviderError,
    LLMRateLimitError,
    get_llm_gateway,
)

logger = logging.getLogger(__name__)

_BASE_SYSTEM_PROMPT = """\
Jesteś asystentem AI wbudowanym w platformę TestGEN — narzędzie do automatycznego \
generowania przypadków testowych i kodu testowego na podstawie analizy kodu \
źródłowego, dokumentacji, diagramów UML i interfejsów graficznych.

Zasady:
- Odpowiadaj ZAWSZE w języku polskim, zwięźle i konkretnie.
- Nie zmyślaj wyników analizy. Jeśli nie masz danych, powiedz to wprost.
- Gdy odwołujesz się do konkretnego obiektu w systemie, użyj znacznika \
@ref:{typ}:{id}, który interfejs zamieni na klikalny odnośnik.

Dozwolone typy referencji:
- @ref:finding:{id} — wynik analizy (podatność lub luka funkcjonalna)
- @ref:tc:{id} — przypadek testowy
- @ref:report:{id} — raport

Przykład: „Najpoważniejsza podatność to SQL injection @ref:finding:42."\
"""

#: Mapowanie wyjątków gatewaya na kod i komunikat prezentowany użytkownikowi.
_ERROR_MESSAGES: dict[str, str] = {
    "rate_limit": "Przekroczono limit zapytań do modelu. Spróbuj ponownie za chwilę.",
    "provider_unavailable": "Usługa modelu jest chwilowo niedostępna. Spróbuj ponownie później.",
    "timeout": "Przekroczono czas oczekiwania na odpowiedź modelu.",
    "llm_error": "Nie udało się uzyskać odpowiedzi od asystenta.",
}


def build_system_prompt(context: ChatContext | None) -> str:
    """Składa system prompt z kontekstem widoku użytkownika (jeśli podano)."""
    if context is None or not (context.project_id or context.view):
        return _BASE_SYSTEM_PROMPT

    lines = ["", "Kontekst użytkownika:"]
    if context.project_id:
        lines.append(f"- identyfikator projektu: {context.project_id}")
    if context.view:
        lines.append(f"- aktualny widok: {context.view}")
    return _BASE_SYSTEM_PROMPT + "\n".join(lines)


def _classify(error: Exception) -> str:
    """Mapuje wyjątek na kod błędu SSE."""
    if isinstance(error, LLMRateLimitError):
        return "rate_limit"
    if isinstance(error, LLMProviderError):
        return "provider_unavailable"
    if isinstance(error, TimeoutError):
        return "timeout"
    return "llm_error"


def _event(name: str, payload: dict) -> str:
    """Formatuje pojedyncze zdarzenie SSE."""
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_chat(
    request: ChatMessageRequest,
    tenant_id=None,
    gateway=None,
    provider: str = "anthropic",
) -> AsyncIterator[str]:
    """Strumieniuje odpowiedź asystenta jako zdarzenia SSE."""
    gateway = gateway or get_llm_gateway()
    conversation_id = request.conversation_id or str(uuid.uuid4())
    system_prompt = build_system_prompt(request.context)
    parts: list[str] = []

    try:
        async for token in gateway.stream_complete(
            provider=provider,
            messages=[LLMMessage(role="user", content=request.message)],
            system_prompt=system_prompt,
            temperature=0.3,
            tenant_id=tenant_id,
            module="chatbot",
            task_type="assistant_answer",
        ):
            parts.append(token)
            yield _event("token", {"content": token})
    except (LLMError, TimeoutError) as exc:
        code = _classify(exc)
        # Komunikat providera może zawierać klucze/URL-e — nie trafia do klienta.
        logger.warning("Chat stream failed (%s): %s", code, exc)
        yield _event("error", {"code": code, "message": _ERROR_MESSAGES[code]})
        return

    yield _event(
        "done",
        {"conversationId": conversation_id, "content": "".join(parts)},
    )
