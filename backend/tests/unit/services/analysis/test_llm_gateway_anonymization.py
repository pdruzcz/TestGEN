"""Testy anonimizacji w LLM Gateway — Story 1.54 (AC: payload bez oryginałów)."""

import json

import httpx
from pydantic import SecretStr

from app.services.analysis.llm_gateway import LLMGateway, LLMMessage, LLMProvider

CODE_WITH_SECRETS = (
    'api_key = "sk-proj-4f8a9b2c7d1e"\nendpoint = "https://api.premium-bank.pl/v1"\ndef verify():\n    return True\n'
)

OPENAI_COMPLETION = json.dumps(
    {
        "choices": [{"message": {"content": "Test dla <SECRET_001> i <URL_001>"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8},
    }
)

ANTHROPIC_COMPLETION = json.dumps(
    {
        "content": [{"type": "text", "text": "Test dla <EMAIL_001>"}],
        "usage": {"input_tokens": 10, "output_tokens": 8},
    }
)


def _gateway_with(body: str = OPENAI_COMPLETION, anonymization: bool = True):
    """Gateway z podstawionym transportem + izolowanymi ustawieniami."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=body.encode())

    gateway = LLMGateway()
    gateway._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway._settings = gateway._settings.model_copy(
        update={
            "openai_api_key": SecretStr("test-openai-key"),
            "anthropic_api_key": SecretStr("test-anthropic-key"),
            "anthropic_proxy_url": "",
            "anthropic_proxy_token": SecretStr(""),
            "anonymization_enabled": anonymization,
        }
    )
    return gateway, seen


class TestOutgoingPayloadAnonymized:
    async def test_secret_and_url_not_in_request_body(self):
        gateway, seen = _gateway_with()
        await gateway.complete(
            provider=LLMProvider.OPENAI,
            messages=[LLMMessage(role="user", content=CODE_WITH_SECRETS)],
            module="test_generation",
        )
        body = json.loads(seen[0].content.decode())
        sent = body["messages"][0]["content"]
        # Asercja AC9: payload wychodzący NIE zawiera oryginalnych wartości
        assert "sk-proj-4f8a9b2c7d1e" not in sent
        assert "https://api.premium-bank.pl/v1" not in sent
        assert "<SECRET_001>" in sent
        assert "<URL_001>" in sent

    async def test_mapping_not_sent_to_llm(self):
        gateway, seen = _gateway_with()
        await gateway.complete(
            provider=LLMProvider.OPENAI,
            messages=[LLMMessage(role="user", content=CODE_WITH_SECRETS)],
        )
        body = json.loads(seen[0].content.decode())
        # Mapping (placeholder → oryginał) nigdy nie opuszcza tenant boundary
        assert "sk-proj-4f8a9b2c7d1e" not in json.dumps(body)

    async def test_anthropic_system_prompt_anonymized(self):
        gateway, seen = _gateway_with(body=ANTHROPIC_COMPLETION)
        await gateway.complete(
            provider=LLMProvider.ANTHROPIC,
            messages=[LLMMessage(role="user", content="analizuj kod")],
            system_prompt="Kontakt: jan.kowalski@premium-bank.pl",
        )
        body = json.loads(seen[0].content.decode())
        assert "jan.kowalski@premium-bank.pl" not in body["system"]
        assert "<EMAIL_001>" in body["system"]


class TestResponseDetokenized:
    async def test_response_placeholders_restored(self):
        gateway, _ = _gateway_with()
        response = await gateway.complete(
            provider=LLMProvider.OPENAI,
            messages=[LLMMessage(role="user", content=CODE_WITH_SECRETS)],
        )
        assert "sk-proj-4f8a9b2c7d1e" in response.content
        assert "https://api.premium-bank.pl/v1" in response.content


class TestDisabledAndFailOpen:
    async def test_disabled_sends_raw(self):
        gateway, seen = _gateway_with(anonymization=False)
        await gateway.complete(
            provider=LLMProvider.OPENAI,
            messages=[LLMMessage(role="user", content=CODE_WITH_SECRETS)],
        )
        sent = json.loads(seen[0].content.decode())["messages"][0]["content"]
        assert "sk-proj-4f8a9b2c7d1e" in sent

    async def test_anonymization_error_fails_open(self, monkeypatch):
        gateway, _ = _gateway_with()

        async def _boom(*args, **kwargs):
            raise RuntimeError("anonymization exploded")

        monkeypatch.setattr("app.services.analysis.anonymization.AnonymizationService.anonymize", _boom)
        response = await gateway.complete(
            provider=LLMProvider.OPENAI,
            messages=[LLMMessage(role="user", content=CODE_WITH_SECRETS)],
        )
        # fail-open: call succeeds (dostępność), błąd zalogowany
        assert response.content == "Test dla <SECRET_001> i <URL_001>"


class TestPlainTextUnaffected:
    async def test_non_sensitive_content_passthrough(self):
        gateway, seen = _gateway_with()
        await gateway.complete(
            provider=LLMProvider.OPENAI,
            messages=[LLMMessage(role="user", content="Ile masz lat?")],
        )
        sent = json.loads(seen[0].content.decode())["messages"][0]["content"]
        assert sent == "Ile masz lat?"
