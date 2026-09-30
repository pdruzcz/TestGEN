"""Tests for the (legacy, gateway-delegating) LLM analysis service.

``analyze_file_content`` now delegates to ``LLMGateway.complete`` — these tests
mock the gateway rather than ``httpx``/``get_settings`` (the old direct-HTTP
implementation was replaced by the unified gateway).
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.analysis.llm_gateway import LLMMessage, LLMProvider, LLMResponse
from app.services.analysis.llm_service import ANALYSIS_SYSTEM_PROMPT, analyze_file_content


def _mock_response(content: str = '{"structures": []}', model: str = "test-model") -> LLMResponse:
    return LLMResponse(
        content=content,
        model=model,
        tokens_input=10,
        tokens_output=20,
        total_tokens=30,
        cost_usd=Decimal("0.001"),
        latency_ms=42,
        provider="anthropic",
    )


@pytest.mark.asyncio
async def test_analyze_file_content_success():
    gateway = MagicMock()
    gateway.complete = AsyncMock(return_value=_mock_response())

    with patch("app.services.analysis.llm_service.get_llm_gateway", return_value=gateway):
        result = await analyze_file_content("test.py", "print('hello')")

    assert result["raw_response"] == '{"structures": []}'
    assert result["model"] == "test-model"
    assert result["usage"]["input_tokens"] == 10
    assert result["usage"]["output_tokens"] == 20
    assert result["usage"]["total_tokens"] == 30
    assert result["cost_usd"] == 0.001
    assert result["latency_ms"] == 42

    gateway.complete.assert_awaited_once()
    kwargs = gateway.complete.await_args.kwargs
    assert kwargs["provider"] == LLMProvider.ANTHROPIC
    assert kwargs["system_prompt"] == ANALYSIS_SYSTEM_PROMPT
    msg = kwargs["messages"][0]
    assert isinstance(msg, LLMMessage)
    assert msg.role == "user"
    assert "test.py" in msg.content
    assert "print('hello')" in msg.content


@pytest.mark.asyncio
async def test_analyze_file_content_sends_filename_and_content():
    gateway = MagicMock()
    gateway.complete = AsyncMock(return_value=_mock_response(content="analysis result"))

    with patch("app.services.analysis.llm_service.get_llm_gateway", return_value=gateway):
        await analyze_file_content("main.py", "def hello(): pass")

    msg = gateway.complete.await_args.kwargs["messages"][0]
    assert "main.py" in msg.content
    assert "def hello(): pass" in msg.content


@pytest.mark.asyncio
async def test_analyze_file_content_api_error_raises():
    gateway = MagicMock()
    gateway.complete = AsyncMock(
        side_effect=httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock(status_code=500))
    )

    with (
        patch("app.services.analysis.llm_service.get_llm_gateway", return_value=gateway),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await analyze_file_content("test.py", "code")


@pytest.mark.asyncio
async def test_analyze_file_content_timeout():
    gateway = MagicMock()
    gateway.complete = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with (
        patch("app.services.analysis.llm_service.get_llm_gateway", return_value=gateway),
        pytest.raises(httpx.TimeoutException),
    ):
        await analyze_file_content("test.py", "code")
