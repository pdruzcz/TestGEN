"""
Unified LLM Gateway supporting OpenAI and Anthropic providers.

Features:
- Retry with exponential backoff
- Model fallback on errors
- Cost tracking and logging
- Provider failover
- Rate limit handling
"""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_incrementing,
)

from app.core.config import get_settings
from app.models.llm_usage import LLMUsage

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMProvider(StrEnum):
    """Available LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, provider: str | None = None, retry_count: int = 0):
        self.message = message
        self.provider = provider
        self.retry_count = retry_count
        super().__init__(message)


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    pass


class LLMProviderError(LLMError):
    """Raised when provider returns an error."""

    pass


@dataclass
class LLMMessage:
    """Message for LLM chat completion."""

    role: str  # system, user, assistant
    content: str


@dataclass
class _StreamUsage:
    """Token counts emitted mid-stream, kept apart from text deltas."""

    tokens_input: int
    tokens_output: int


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str
    model: str
    tokens_input: int
    tokens_output: int
    total_tokens: int
    cost_usd: Decimal
    latency_ms: int
    provider: str
    fallback: bool = False
    raw_response: dict | None = None


# Cost per 1M tokens (approximate, update as needed)
TOKEN_COSTS = {
    "openai": {
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    },
}


def calculate_cost(provider: str, model: str, tokens_input: int, tokens_output: int) -> Decimal:
    """Calculate cost in USD for given token usage."""
    provider_costs = TOKEN_COSTS.get(provider, {})
    model_costs = provider_costs.get(model, {"input": 0.0, "output": 0.0})
    cost = Decimal(tokens_input) / 1_000_000 * Decimal(str(model_costs["input"])) + Decimal(
        tokens_output
    ) / 1_000_000 * Decimal(str(model_costs["output"]))
    return cost.quantize(Decimal("0.000001"))


class LLMGateway:
    """Unified LLM Gateway with multi-provider support."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._settings = get_settings()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            timeout = httpx.Timeout(self._settings.llm_timeout, connect=10.0)
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def complete(
        self,
        provider: LLMProvider | str,
        messages: list[LLMMessage] | list[dict],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tenant_id: int | None = None,
        module: str = "unknown",
        task_type: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str | None = None,
        stream: bool = False,
    ) -> LLMResponse:
        """
        Complete a chat request with specified provider.

        Args:
            provider: LLM provider to use (openai, anthropic)
            messages: List of message dicts or LLMMessage objects
            model: Model to use (defaults to provider's default)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            tenant_id: Tenant ID for usage tracking
            module: Module name for logging (code_analysis, etc.)
            task_type: Task type for logging
            prompt_version: Prompt version for A/B testing
            system_prompt: System prompt (for Anthropic compatibility)
            stream: Whether to stream response (not yet implemented)

        Returns:
            LLMResponse with standardized format

        Raises:
            LLMError: If request fails after retries
            LLMRateLimitError: If rate limit is exceeded
        """
        if isinstance(provider, str):
            provider = LLMProvider(provider)

        # Normalize messages — always copy, never alias caller dicts
        # (anonymization below mutates them in place).
        normalized_messages = [
            {"role": msg["role"], "content": msg["content"]}
            if isinstance(msg, dict)
            else {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Story 1.54 (FR72): mask sensitive values before they leave the tenant.
        service, mapping, system_prompt = await self._anonymize_outbound(normalized_messages, system_prompt)

        # Select implementation based on provider
        if provider == LLMProvider.OPENAI:
            response = await self._complete_openai(
                messages=normalized_messages,
                model=model or self._settings.openai_default_model,
                max_tokens=max_tokens,
                temperature=temperature,
                tenant_id=tenant_id,
                module=module,
                task_type=task_type,
                prompt_version=prompt_version,
            )
        elif provider == LLMProvider.ANTHROPIC:
            response = await self._complete_anthropic(
                messages=normalized_messages,
                model=model or self._settings.anthropic_default_model,
                max_tokens=max_tokens,
                temperature=temperature,
                tenant_id=tenant_id,
                module=module,
                task_type=task_type,
                prompt_version=prompt_version,
                system_prompt=system_prompt,
            )
        else:
            raise LLMError(f"Unknown provider: {provider}")

        if mapping:
            # Detokenize the provider output before it reaches the caller.
            response.content = await service.deanonymize(response.content, mapping)
        return response

    async def _anonymize_outbound(
        self, messages: list[dict], system_prompt: str | None
    ) -> tuple[object | None, dict[str, str], str | None]:
        """Mask secrets/URLs/e-mails/IPs in outbound payload (Story 1.54).

        Single choke point covering every LLM call in the platform. The
        mapping stays in memory for this call only — it is never persisted
        here and never sent to the provider. Fail-open: an anonymization bug
        logs an error but does not take down LLM features (the pipeline-level
        anonymization enforces FR72 for the code-analysis path).
        """
        if not self._settings.anonymization_enabled:
            return None, {}, system_prompt
        try:
            from app.services.analysis.anonymization import AnonymizationService

            service = AnonymizationService()
            mapping: dict[str, str] = {}
            for msg in messages:
                anonymized, msg_map = await service.anonymize(msg["content"])
                msg["content"] = anonymized
                mapping.update(msg_map)
            if system_prompt:
                anonymized, prompt_map = await service.anonymize(system_prompt)
                mapping.update(prompt_map)
                system_prompt = anonymized
            return service, mapping, system_prompt
        except Exception as exc:
            logger.error("Anonymization failed — payload sent unmasked (fail-open): %s", exc)
            return None, {}, system_prompt

    async def stream_complete(
        self,
        provider: LLMProvider | str,
        messages: list[LLMMessage] | list[dict],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tenant_id=None,
        module: str = "unknown",
        task_type: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion token by token (Story 6.14, AC7).

        Yields text deltas as they arrive. Usage is logged once the stream
        completes; a stream aborted by the client logs nothing.

        Raises:
            LLMRateLimitError: provider returned HTTP 429
            LLMProviderError: provider returned HTTP 5xx
            LLMError: any other failure (bad key, unknown provider)
        """
        if isinstance(provider, str):
            provider = LLMProvider(provider)

        normalized_messages = [
            msg if isinstance(msg, dict) else {"role": msg.role, "content": msg.content} for msg in messages
        ]

        if provider == LLMProvider.OPENAI:
            stream = self._stream_openai(
                messages=normalized_messages,
                model=model or self._settings.openai_default_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
            )
        elif provider == LLMProvider.ANTHROPIC:
            stream = self._stream_anthropic(
                messages=normalized_messages,
                model=model or self._settings.anthropic_default_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
            )
        else:
            raise LLMError(f"Unknown provider: {provider}")

        import time

        start_time = time.time()
        resolved_model = model or (
            self._settings.openai_default_model
            if provider == LLMProvider.OPENAI
            else self._settings.anthropic_default_model
        )
        tokens_input = 0
        tokens_output = 0

        async for chunk in stream:
            if isinstance(chunk, _StreamUsage):
                tokens_input = chunk.tokens_input or tokens_input
                tokens_output = chunk.tokens_output or tokens_output
                continue
            yield chunk

        await self._log_usage(
            tenant_id=tenant_id,
            provider=provider.value,
            model=resolved_model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=calculate_cost(provider.value, resolved_model, tokens_input, tokens_output),
            latency_ms=int((time.time() - start_time) * 1000),
            module=module,
            task_type=task_type,
            prompt_version=prompt_version,
        )

    async def _stream_openai(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str | None,
    ) -> AsyncIterator["str | _StreamUsage"]:
        """Parse OpenAI's `data: {...}` SSE stream into text deltas."""
        api_key = self._settings.openai_api_key.get_secret_value()
        if not api_key:
            raise LLMError("OpenAI API key not configured")

        payload_messages = [{"role": "system", "content": system_prompt}, *messages] if system_prompt else messages
        client = await self._get_client()

        async with client.stream(
            "POST",
            f"{self._settings.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": payload_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                "stream_options": {"include_usage": True},
            },
        ) as response:
            self._raise_for_stream_status(response, "openai")

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line.removeprefix("data: ").strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Malformed OpenAI stream chunk skipped")
                    continue

                if usage := event.get("usage"):
                    yield _StreamUsage(
                        tokens_input=usage.get("prompt_tokens", 0),
                        tokens_output=usage.get("completion_tokens", 0),
                    )

                for choice in event.get("choices", []):
                    if content := choice.get("delta", {}).get("content"):
                        yield content

    async def _stream_anthropic(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str | None,
    ) -> AsyncIterator["str | _StreamUsage"]:
        """Parse Anthropic's named-event SSE stream into text deltas."""
        if self._settings.anthropic_proxy_url and self._settings.anthropic_proxy_token.get_secret_value():
            base_url = self._settings.anthropic_proxy_url
            api_key = self._settings.anthropic_proxy_token.get_secret_value()
        else:
            base_url = self._settings.anthropic_base_url
            api_key = self._settings.anthropic_api_key.get_secret_value()

        if not api_key:
            raise LLMError("Anthropic API key not configured")

        system_content = system_prompt or ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content += "\n" + msg["content"]
            else:
                user_messages.append(msg)

        client = await self._get_client()

        async with client.stream(
            "POST",
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": user_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_content,
                "stream": True,
            },
        ) as response:
            self._raise_for_stream_status(response, "anthropic")

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line.removeprefix("data: ").strip())
                except json.JSONDecodeError:
                    logger.warning("Malformed Anthropic stream chunk skipped")
                    continue

                delta = event.get("delta", {})
                if delta.get("type") == "text_delta" and (text := delta.get("text")):
                    yield text

                # message_start carries input tokens, message_delta the output count.
                if message := event.get("message"):
                    usage = message.get("usage", {})
                    yield _StreamUsage(
                        tokens_input=usage.get("input_tokens", 0),
                        tokens_output=usage.get("output_tokens", 0),
                    )
                elif "delta" in event and (usage := event.get("usage")):
                    yield _StreamUsage(
                        tokens_input=0,
                        tokens_output=usage.get("output_tokens", 0),
                    )

    @staticmethod
    def _raise_for_stream_status(response: httpx.Response, provider: str) -> None:
        """Translate HTTP status of a streaming response into gateway errors."""
        if response.status_code == 429:
            logger.warning("%s rate limit exceeded (stream)", provider)
            raise LLMRateLimitError(f"{provider} rate limit", provider)
        if response.status_code >= 500:
            logger.warning("%s server error %s (stream)", provider, response.status_code)
            raise LLMProviderError(f"{provider} server error: {response.status_code}", provider)
        if response.status_code >= 400:
            raise LLMError(f"{provider} stream request failed: {response.status_code}", provider)

    @retry(
        retry=retry_if_exception_type((LLMProviderError, LLMRateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_incrementing(start=5, increment=10),
    )
    async def _complete_openai(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        tenant_id: int | None,
        module: str,
        task_type: str | None,
        prompt_version: str | None,
        attempt: int = 1,
    ) -> LLMResponse:
        """Complete request with OpenAI API."""
        import time

        start_time = time.time()

        api_key = self._settings.openai_api_key.get_secret_value()
        if not api_key:
            raise LLMError("OpenAI API key not configured")

        client = await self._get_client()

        try:
            response = await client.post(
                f"{self._settings.openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            data = response.json()

            usage = data.get("usage", {})
            tokens_input = usage.get("prompt_tokens", 0)
            tokens_output = usage.get("completion_tokens", 0)
            content = data["choices"][0]["message"]["content"]

            latency_ms = int((time.time() - start_time) * 1000)
            cost = calculate_cost("openai", model, tokens_input, tokens_output)

            # Log usage
            await self._log_usage(
                tenant_id=tenant_id,
                provider="openai",
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost_usd=cost,
                latency_ms=latency_ms,
                module=module,
                task_type=task_type,
                prompt_version=prompt_version,
            )

            return LLMResponse(
                content=content,
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                total_tokens=tokens_input + tokens_output,
                cost_usd=cost,
                latency_ms=latency_ms,
                provider="openai",
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"OpenAI rate limit exceeded (attempt {attempt})")
                raise LLMRateLimitError(f"OpenAI rate limit: {e}", "openai", attempt) from e
            elif e.response.status_code >= 500:
                logger.warning(f"OpenAI server error: {e.response.status_code} (attempt {attempt})")
                # Try fallback model on subsequent attempts
                if attempt > 1 and model != self._settings.openai_fallback_model:
                    logger.info(f"Falling back to {self._settings.openai_fallback_model}")
                    return await self._complete_openai(
                        messages=messages,
                        model=self._settings.openai_fallback_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        tenant_id=tenant_id,
                        module=module,
                        task_type=task_type,
                        prompt_version=prompt_version,
                        attempt=attempt + 1,
                    )
                raise LLMProviderError(f"OpenAI server error: {e}", "openai", attempt) from e
            else:
                raise LLMError(f"OpenAI request failed: {e}", "openai", attempt) from e

    @retry(
        retry=retry_if_exception_type((LLMProviderError, LLMRateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_incrementing(start=5, increment=10),
    )
    async def _complete_anthropic(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        tenant_id: int | None,
        module: str,
        task_type: str | None,
        prompt_version: str | None,
        system_prompt: str | None,
        attempt: int = 1,
    ) -> LLMResponse:
        """Complete request with Anthropic API."""
        import time

        start_time = time.time()

        # Try proxy first if configured
        if self._settings.anthropic_proxy_url and self._settings.anthropic_proxy_token.get_secret_value():
            base_url = self._settings.anthropic_proxy_url
            api_key = self._settings.anthropic_proxy_token.get_secret_value()
        else:
            base_url = self._settings.anthropic_base_url
            api_key = self._settings.anthropic_api_key.get_secret_value()

        if not api_key:
            raise LLMError("Anthropic API key not configured")

        client = await self._get_client()

        # Extract system prompt if provided
        system_content = system_prompt or ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_content += "\n" + msg["content"]
            else:
                user_messages.append(msg)

        try:
            response = await client.post(
                f"{base_url}/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": user_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_content,
                },
            )
            response.raise_for_status()
            data = response.json()

            usage = data.get("usage", {})
            tokens_input = usage.get("input_tokens", 0)
            tokens_output = usage.get("output_tokens", 0)
            content = data["content"][0]["text"]

            latency_ms = int((time.time() - start_time) * 1000)
            cost = calculate_cost("anthropic", model, tokens_input, tokens_output)

            # Log usage
            await self._log_usage(
                tenant_id=tenant_id,
                provider="anthropic",
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost_usd=cost,
                latency_ms=latency_ms,
                module=module,
                task_type=task_type,
                prompt_version=prompt_version,
            )

            return LLMResponse(
                content=content,
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                total_tokens=tokens_input + tokens_output,
                cost_usd=cost,
                latency_ms=latency_ms,
                provider="anthropic",
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"Anthropic rate limit exceeded (attempt {attempt})")
                raise LLMRateLimitError(f"Anthropic rate limit: {e}", "anthropic", attempt) from e
            elif e.response.status_code >= 500:
                logger.warning(f"Anthropic server error: {e.response.status_code} (attempt {attempt})")
                raise LLMProviderError(f"Anthropic server error: {e}", "anthropic", attempt) from e
            else:
                raise LLMError(f"Anthropic request failed: {e}", "anthropic", attempt) from e

    async def _log_usage(
        self,
        tenant_id: int | None,
        provider: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        cost_usd: Decimal,
        latency_ms: int,
        module: str,
        task_type: str | None,
        prompt_version: str | None,
    ):
        """Log LLM usage to database for cost tracking."""
        if tenant_id is None:
            return

        try:
            from sqlalchemy import select

            from app.core.database import get_sync_session
            from app.models.tenant import Tenant

            with get_sync_session() as db:
                # Check tenant cost limits
                tenant = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
                if not tenant:
                    logger.warning(f"Tenant {tenant_id} not found for usage logging")
                    return

                # Calculate current month's cost
                from sqlalchemy import func

                current_cost = db.execute(
                    select(func.sum(LLMUsage.cost_usd)).where(LLMUsage.tenant_id == tenant_id)
                ).scalar() or Decimal("0")

                # Determine limit based on plan (model 3-planowy: freemium/paid)
                limit = (
                    self._settings.llm_cost_limit_professional
                    if tenant.plan in ("basic", "premium")
                    else self._settings.llm_cost_limit_basic
                )

                # Check if approaching limit
                threshold = limit * self._settings.llm_alert_threshold
                if current_cost >= threshold:
                    logger.warning(
                        f"Tenant {tenant_id} at {current_cost}/{limit} USD ({current_cost / limit * 100:.0f}%)"
                    )
                    # TODO: Send alert notification (FR59)

                # Block if over limit
                if current_cost >= limit:
                    logger.error(f"Tenant {tenant_id} exceeded LLM cost limit: {current_cost}/{limit}")
                    raise LLMError(f"Monthly LLM cost limit exceeded: {current_cost:.2f}/{limit:.2f} USD")

                # Log usage
                usage = LLMUsage(
                    tenant_id=tenant_id,
                    provider=provider,
                    model=model,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    total_tokens=tokens_input + tokens_output,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    module=module,
                    task_type=task_type,
                    prompt_version=prompt_version,
                )
                db.add(usage)
                db.commit()

        except Exception as e:
            logger.error(f"Failed to log LLM usage: {e}")

    async def check_cost_limit(self, tenant_id: int) -> tuple[bool, Decimal, Decimal]:
        """
        Check if tenant is within LLM cost limits.

        Returns:
            (allowed, current_cost, limit)
        """
        from sqlalchemy import func, select

        from app.core.database import get_sync_session
        from app.models.tenant import Tenant

        with get_sync_session() as db:
            tenant = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
            if not tenant:
                raise LLMError(f"Tenant {tenant_id} not found")

            limit = (
                self._settings.llm_cost_limit_professional
                if tenant.plan in ("basic", "premium")
                else self._settings.llm_cost_limit_basic
            )

            current_cost = db.execute(
                select(func.sum(LLMUsage.cost_usd)).where(LLMUsage.tenant_id == tenant_id)
            ).scalar() or Decimal("0")

            return (current_cost < limit, current_cost, Decimal(str(limit)))


# Global gateway instance
_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    """Get or create global LLM gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
