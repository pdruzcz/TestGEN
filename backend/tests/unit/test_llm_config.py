"""Tests for LLM configuration (Anthropic + OpenAI gateway settings)."""

from pydantic import SecretStr

from app.core.config import Settings

_DB = "postgresql+asyncpg://test:test@localhost/test"


def test_llm_settings_default_values():
    # Assert the defaults DECLARED IN CODE (via model_fields), so the test is
    # immune to a developer's local .env leaking ANTHROPIC_* into the process.
    defaults = {name: field.default for name, field in Settings.model_fields.items()}
    assert defaults["anthropic_api_key"] == SecretStr("")
    assert defaults["anthropic_base_url"] == "https://api.anthropic.com/v1"
    assert defaults["anthropic_default_model"] == "claude-sonnet-4-20250514"
    assert defaults["anthropic_proxy_url"] == ""
    assert defaults["anthropic_proxy_token"] == SecretStr("")
    assert defaults["openai_default_model"] == "gpt-4o"


def test_llm_settings_from_env():
    settings = Settings(
        _env_file=None,
        database_url=_DB,
        anthropic_api_key="test-key-123",
        anthropic_base_url="https://custom.api/v1",
        anthropic_default_model="claude-opus-4",
        anthropic_proxy_url="https://api.z.ai/api/anthropic",
        anthropic_proxy_token="proxy-tok",
    )
    assert settings.anthropic_api_key.get_secret_value() == "test-key-123"
    assert settings.anthropic_base_url == "https://custom.api/v1"
    assert settings.anthropic_default_model == "claude-opus-4"
    assert settings.anthropic_proxy_url == "https://api.z.ai/api/anthropic"
    assert settings.anthropic_proxy_token.get_secret_value() == "proxy-tok"


def test_anthropic_api_key_is_secret():
    settings = Settings(
        _env_file=None,
        database_url=_DB,
        anthropic_api_key="sensitive-value",
    )
    assert "sensitive-value" not in str(settings.anthropic_api_key)
    assert settings.anthropic_api_key.get_secret_value() == "sensitive-value"


def test_anthropic_proxy_token_is_secret():
    settings = Settings(
        _env_file=None,
        database_url=_DB,
        anthropic_proxy_token="proxy-secret",
    )
    assert "proxy-secret" not in str(settings.anthropic_proxy_token)
    assert settings.anthropic_proxy_token.get_secret_value() == "proxy-secret"
