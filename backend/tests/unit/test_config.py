from app.core.config import EngineMode, Settings


def test_settings_default_values():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
    )
    assert settings.app_name == "TestGEN"
    assert settings.app_env == "development"
    assert settings.debug is False
    assert settings.engine_mode == EngineMode.HYBRID
    assert settings.backend_port == 8000


def test_settings_loads_custom_values():
    settings = Settings(
        _env_file=None,
        app_name="TestGEN-Custom",
        debug=True,
        engine_mode="native",
        database_url="postgresql+asyncpg://custom:custom@db/custom",
        redis_url="redis://custom-redis:6379/0",
    )
    assert settings.app_name == "TestGEN-Custom"
    assert settings.debug is True
    assert settings.engine_mode == EngineMode.NATIVE
    assert "custom" in settings.database_url
    assert "custom-redis" in settings.redis_url


def test_settings_cors_origins_default():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
    )
    assert "http://localhost:4200" in settings.cors_origins
    assert "http://localhost:8000" in settings.cors_origins
    assert "http://localhost:4200" in settings.cors_origins_list
    assert "http://localhost:8000" in settings.cors_origins_list
