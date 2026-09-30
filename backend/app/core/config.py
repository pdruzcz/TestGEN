from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineMode(StrEnum):
    NATIVE = "native"
    LLM = "llm"
    HYBRID = "hybrid"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "TestGEN"
    app_env: str = "development"
    debug: bool = False
    engine_mode: EngineMode = EngineMode.HYBRID

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # JWT (RS256)
    jwt_private_key_path: Path = Path("keys/private.pem")
    jwt_public_key_path: Path = Path("keys/public.pem")
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Database
    database_url: str = "postgresql+asyncpg://testgen:testgen_dev_password@postgres:5432/testgen"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # RabbitMQ
    rabbitmq_url: str = "amqp://testgen:testgen_dev_password@rabbitmq:5672//"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "testgen"
    minio_root_password: str = "testgen_dev_password"
    minio_use_ssl: bool = False
    minio_bucket_name: str = "testgen-files"

    # File upload limits (per plan, MB per single file)
    max_file_size_basic_mb: int = 100
    max_file_size_professional_mb: int = 500

    # Archive extraction limits (Story 1.6-zakańczenie) — guard the synchronous
    # upload/git extraction path against zip-bombs and runaway file counts.
    archive_max_compressed_mb: int = 600  # >= professional upload cap (500)
    archive_max_extracted_mb: int = 1024  # decompressed total per archive
    archive_max_file_count: int = 10000  # max files extracted from one archive

    # Git clone
    git_clone_timeout_seconds: int = 300

    # Integracje SCM — GitHub OAuth App (Epic 8, Story 8.1).
    # Puste client_id wyłącza integrację: endpoint /authorize zwraca wtedy 503
    # zamiast odsyłać użytkownika na GitHuba z pustym parametrem.
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")
    github_redirect_uri: str = "http://localhost:8000/api/v1/integrations/github/callback"
    # Publiczny adres API — GitHub musi trafić z powrotem webhookiem, więc
    # localhost zadziała tylko za tunelem (ngrok itp.).
    api_public_base_url: str = "http://localhost:8000"
    github_api_url: str = "https://api.github.com"
    github_oauth_base_url: str = "https://github.com"
    # Integracje SCM — GitLab OAuth Application (Epic 8, Story 8.2).
    # ``gitlab_default_url`` to tylko wartość domyślna formularza; faktyczny
    # adres instancji zapisujemy per integracja (self-hosted).
    gitlab_client_id: str = ""
    gitlab_client_secret: SecretStr = SecretStr("")
    gitlab_redirect_uri: str = "http://localhost:8000/api/v1/integrations/gitlab/callback"
    gitlab_default_url: str = "https://gitlab.com"

    # Gałęzie, których push uruchamia analizę (AC3).
    scm_analyzed_branches: list[str] = ["main", "master"]

    # LLM Gateway — OpenAI
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    openai_default_model: str = "gpt-4o"
    openai_fallback_model: str = "gpt-4o-mini"

    # LLM Gateway — Anthropic
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_default_model: str = "claude-sonnet-4-20250514"
    # For Anthropic-compatible proxy (e.g., z.ai)
    anthropic_proxy_url: str = ""
    anthropic_proxy_token: SecretStr = SecretStr("")

    # LLM cost limits per tenant (USD)
    llm_cost_limit_basic: float = 100.0
    llm_cost_limit_professional: float = 1000.0
    llm_alert_threshold: float = 0.8  # 80%

    # LLM retry configuration
    llm_max_retries: int = 3
    llm_retry_delays: list[int] = [5, 15, 45]  # exponential backoff in seconds
    llm_timeout: int = 60

    # Anonymization of client code before cloud (LLM) analysis — Story 1.54 (FR72)
    anonymization_enabled: bool = True  # domyślnie ON dla ścieżki LLM w SaaS
    anonymization_confidence_threshold: float = 0.7  # LLM detection threshold
    # Retencja mappingu (hours) — spójna z 1.49 (24h Professional)
    anonymization_retention_hours: int = 24

    # Prompt repository
    prompts_dir: Path = Path("backend/app/prompts")

    # Celery
    celery_broker_url: str = "amqp://testgen:testgen_dev_password@rabbitmq:5672//"
    celery_result_backend: str = "redis://redis:6379/1"
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: list[str] = ["json"]
    celery_timezone: str = "UTC"
    celery_soft_time_limit: int = 300
    celery_hard_time_limit: int = 330
    celery_max_retries: int = 3
    celery_retry_delays: list[int] = [10, 60, 300]

    # CORS
    cors_origins: str = "http://localhost:4200,http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]

    # Cookies
    cookie_secure: bool = False
    cookie_domain: str | None = None

    # MFA
    mfa_token_expire_minutes: int = 5
    # Fernet key for encrypting TOTP secrets at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # MUST be overridden in production via ENCRYPTION_KEY env var!
    encryption_key: str = (
        "xgJoA_rOWIHC-_Ezc_G_x3fk0RLVK38icOUCMDTY914="  # dev-only default — MUST override in production
    )

    # Admin bootstrap
    bootstrap_admin: bool = False
    admin_email: str = ""
    admin_password: str = ""

    # Brute force protection
    max_login_attempts: int = 5
    account_lockout_minutes: int = 30
    login_attempts_window_minutes: int = 15
    mfa_attempts_window_minutes: int = 15

    # Email — Microsoft Graph API (OAuth2 Client Credentials)
    # smtp_user = mailbox UPN used in Graph API URL (e.g. testgen@nexio.pl)
    smtp_user: str = ""
    smtp_from_email: str = "noreply@testgen.io"
    ms_tenant_id: str = ""
    ms_client_id: str = ""
    ms_client_secret: SecretStr = SecretStr("")
    email_verification_url_template: str = "http://localhost:4200/verify-email?token={token}"
    email_invitation_url_template: str = "http://localhost:4200/set-password?token={token}"
    email_password_reset_url_template: str = "http://localhost:4200/reset-password?token={token}"
    # Baza URL frontendu do CTA w emailach (Story 7.11 — „Uaktualnij plan").
    frontend_base_url: str = "http://localhost:4200"

    _DEV_ENCRYPTION_KEY = "xgJoA_rOWIHC-_Ezc_G_x3fk0RLVK38icOUCMDTY914="

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        if self.app_env != "development" and self.encryption_key == self._DEV_ENCRYPTION_KEY:
            raise ValueError(
                "ENCRYPTION_KEY must be changed from default in non-development environments. "
                'Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
