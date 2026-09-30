"""Testy serwisu czatu AI Assistant — Story 6.14, Task 8 (AC2, AC7)."""

import json
from collections.abc import AsyncIterator

import pytest

from app.schemas.chat import ChatContext, ChatMessageRequest
from app.services.analysis.llm_gateway import (
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
)
from app.services.chat import chat_service


class _FakeGateway:
    """Gateway zwracający zadane tokeny albo podnoszący wyjątek."""

    def __init__(self, tokens: list[str] | None = None, error: Exception | None = None):
        self._tokens = tokens or []
        self._error = error
        self.calls: list[dict] = []

    async def stream_complete(self, **kwargs) -> AsyncIterator[str]:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        for token in self._tokens:
            yield token


def _parse_events(raw: str) -> list[tuple[str, dict]]:
    """Rozbija surowy strumień SSE na pary (event, data)."""
    events: list[tuple[str, dict]] = []
    for block in raw.strip().split("\n\n"):
        if not block.strip():
            continue
        name = ""
        payload = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                payload = line.removeprefix("data: ")
        events.append((name, json.loads(payload)))
    return events


class TestBuildSystemPrompt:
    def test_wymusza_jezyk_polski(self):
        prompt = chat_service.build_system_prompt(None)
        assert "języku polskim" in prompt

    def test_opisuje_format_referencji(self):
        prompt = chat_service.build_system_prompt(None)
        assert "@ref:" in prompt
        assert "@ref:tc:" in prompt

    def test_dodaje_kontekst_projektu(self):
        prompt = chat_service.build_system_prompt(
            ChatContext(project_id="a3f1", view="Wyniki analizy")
        )
        assert "a3f1" in prompt
        assert "Wyniki analizy" in prompt

    def test_bez_kontekstu_nie_zawiera_sekcji_kontekstu(self):
        assert "Kontekst użytkownika" not in chat_service.build_system_prompt(None)


class TestStreamChat:
    async def _collect(self, gateway, message="Ile mam luk?", context=None) -> str:
        request = ChatMessageRequest(message=message, context=context)
        chunks = [
            chunk
            async for chunk in chat_service.stream_chat(
                request=request, tenant_id=None, gateway=gateway
            )
        ]
        return "".join(chunks)

    async def test_emituje_tokeny_w_kolejnosci(self):
        gateway = _FakeGateway(tokens=["Masz ", "3 ", "luki."])
        events = _parse_events(await self._collect(gateway))

        tokens = [data["content"] for name, data in events if name == "token"]
        assert tokens == ["Masz ", "3 ", "luki."]

    async def test_konczy_zdarzeniem_done_z_pelna_trescia(self):
        gateway = _FakeGateway(tokens=["Ala ", "ma kota"])
        events = _parse_events(await self._collect(gateway))

        name, data = events[-1]
        assert name == "done"
        assert data["content"] == "Ala ma kota"
        assert data["conversationId"]

    async def test_zachowuje_conversation_id_z_zadania(self):
        gateway = _FakeGateway(tokens=["ok"])
        request = ChatMessageRequest(message="test", conversation_id="conv-7")
        events = _parse_events(
            "".join(
                [
                    chunk
                    async for chunk in chat_service.stream_chat(
                        request=request, tenant_id=None, gateway=gateway
                    )
                ]
            )
        )
        assert events[-1][1]["conversationId"] == "conv-7"

    async def test_przekazuje_system_prompt_i_modul_do_gateway(self):
        gateway = _FakeGateway(tokens=["x"])
        await self._collect(gateway, context=ChatContext(project_id="p1"))

        call = gateway.calls[0]
        assert call["module"] == "chatbot"
        assert "języku polskim" in call["system_prompt"]
        assert "p1" in call["system_prompt"]

    @pytest.mark.parametrize(
        ("error", "expected_code"),
        [
            (LLMRateLimitError("limit", "openai"), "rate_limit"),
            (LLMProviderError("5xx", "openai"), "provider_unavailable"),
            (LLMError("brak klucza"), "llm_error"),
            (TimeoutError(), "timeout"),
        ],
    )
    async def test_mapuje_bledy_na_zdarzenie_error(self, error, expected_code):
        gateway = _FakeGateway(error=error)
        events = _parse_events(await self._collect(gateway))

        name, data = events[-1]
        assert name == "error"
        assert data["code"] == expected_code
        assert data["message"]

    async def test_komunikat_bledu_jest_po_polsku(self):
        gateway = _FakeGateway(error=LLMRateLimitError("limit", "openai"))
        events = _parse_events(await self._collect(gateway))
        assert "Przekroczono" in events[-1][1]["message"]

    async def test_nie_ujawnia_szczegolow_technicznych_bledu(self):
        gateway = _FakeGateway(error=LLMProviderError("api_key=sk-tajne", "openai"))
        events = _parse_events(await self._collect(gateway))
        assert "sk-tajne" not in events[-1][1]["message"]


class TestChatMessageRequest:
    def test_odrzuca_pusta_wiadomosc(self):
        with pytest.raises(ValueError):
            ChatMessageRequest(message="")

    def test_odrzuca_zbyt_dluga_wiadomosc(self):
        with pytest.raises(ValueError):
            ChatMessageRequest(message="x" * 4001)
