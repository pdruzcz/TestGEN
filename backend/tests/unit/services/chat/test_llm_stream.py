"""Testy streamingu LLM Gateway — Story 6.14, Task 8 (AC7).

Weryfikują parsowanie strumieni SSE providerów OpenAI i Anthropic.
"""

import httpx
import pytest
from pydantic import SecretStr

from app.services.analysis.llm_gateway import (
    LLMGateway,
    LLMMessage,
    LLMProviderError,
    LLMRateLimitError,
)

OPENAI_STREAM = (
    b'data: {"choices":[{"delta":{"content":"Masz "}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":"3 luki"}}]}\n\n'
    b'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":11,"completion_tokens":4}}\n\n'
    b"data: [DONE]\n\n"
)

ANTHROPIC_STREAM = (
    b"event: message_start\n"
    b'data: {"message":{"usage":{"input_tokens":11,"output_tokens":0}}}\n\n'
    b"event: content_block_delta\n"
    b'data: {"delta":{"type":"text_delta","text":"Masz "}}\n\n'
    b"event: content_block_delta\n"
    b'data: {"delta":{"type":"text_delta","text":"3 luki"}}\n\n'
    b"event: message_delta\n"
    b'data: {"usage":{"output_tokens":4}}\n\n'
    b"event: message_stop\n"
    b"data: {}\n\n"
)


def _gateway_with(body: bytes, status: int = 200) -> tuple[LLMGateway, list[httpx.Request]]:
    """Gateway z podstawionym transportem HTTP zwracającym zadany strumień."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, content=body)

    gateway = LLMGateway()
    gateway._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    # Izolowana kopia ustawień — testy nie zależą od kluczy w środowisku
    # i nie modyfikują współdzielonego obiektu Settings.
    gateway._settings = gateway._settings.model_copy(
        update={
            "openai_api_key": SecretStr("test-openai-key"),
            "anthropic_api_key": SecretStr("test-anthropic-key"),
            "anthropic_proxy_url": "",
            "anthropic_proxy_token": SecretStr(""),
        }
    )
    return gateway, seen


async def _collect(gateway: LLMGateway, provider: str) -> list[str]:
    return [
        token
        async for token in gateway.stream_complete(
            provider=provider,
            messages=[LLMMessage(role="user", content="Ile mam luk?")],
            system_prompt="Odpowiadaj po polsku.",
            module="chatbot",
        )
    ]


class TestStreamOpenAI:
    async def test_zwraca_kolejne_delty_tekstu(self):
        gateway, _ = _gateway_with(OPENAI_STREAM)
        assert await _collect(gateway, "openai") == ["Masz ", "3 luki"]

    async def test_wysyla_flage_stream(self):
        gateway, seen = _gateway_with(OPENAI_STREAM)
        await _collect(gateway, "openai")

        import json

        payload = json.loads(seen[0].content)
        assert payload["stream"] is True

    async def test_pomija_sentinel_done(self):
        gateway, _ = _gateway_with(OPENAI_STREAM)
        assert "[DONE]" not in "".join(await _collect(gateway, "openai"))

    async def test_rate_limit_podnosi_wyjatek(self):
        gateway, _ = _gateway_with(b"", status=429)
        with pytest.raises(LLMRateLimitError):
            await _collect(gateway, "openai")

    async def test_blad_serwera_podnosi_wyjatek(self):
        gateway, _ = _gateway_with(b"", status=503)
        with pytest.raises(LLMProviderError):
            await _collect(gateway, "openai")


class TestStreamAnthropic:
    async def test_zwraca_kolejne_delty_tekstu(self):
        gateway, _ = _gateway_with(ANTHROPIC_STREAM)
        assert await _collect(gateway, "anthropic") == ["Masz ", "3 luki"]

    async def test_przekazuje_system_prompt_osobnym_polem(self):
        gateway, seen = _gateway_with(ANTHROPIC_STREAM)
        await _collect(gateway, "anthropic")

        import json

        payload = json.loads(seen[0].content)
        assert payload["system"] == "Odpowiadaj po polsku."
        assert payload["stream"] is True

    async def test_ignoruje_zdarzenia_bez_tekstu(self):
        gateway, _ = _gateway_with(ANTHROPIC_STREAM)
        assert all(token for token in await _collect(gateway, "anthropic"))

    async def test_rate_limit_podnosi_wyjatek(self):
        gateway, _ = _gateway_with(b"", status=429)
        with pytest.raises(LLMRateLimitError):
            await _collect(gateway, "anthropic")
