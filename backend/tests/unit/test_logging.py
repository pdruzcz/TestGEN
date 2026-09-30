import json
import logging
from unittest.mock import patch

from app.core.config import Settings


def _make_settings(**overrides):
    defaults = {
        "_env_file": None,
        "database_url": "postgresql+asyncpg://test:test@localhost/test",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@patch("app.core.logging.get_settings")
def test_setup_logging_returns_logger(mock_settings):
    mock_settings.return_value = _make_settings(debug=True)
    from app.core.logging import setup_logging

    logger = setup_logging()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "testgen"


@patch("app.core.logging.get_settings")
def test_setup_logging_debug_level(mock_settings):
    mock_settings.return_value = _make_settings(debug=True)
    from app.core.logging import setup_logging

    logger = setup_logging()
    assert logger.level == logging.DEBUG


@patch("app.core.logging.get_settings")
def test_setup_logging_info_level_when_not_debug(mock_settings):
    mock_settings.return_value = _make_settings(debug=False)
    from app.core.logging import setup_logging

    logger = setup_logging()
    assert logger.level == logging.INFO


@patch("app.core.logging.get_settings")
def test_setup_logging_json_output(mock_settings, capsys):
    mock_settings.return_value = _make_settings(debug=True)
    from app.core.logging import setup_logging

    logger = setup_logging()
    logger.info("test message")

    captured = capsys.readouterr()
    log_entry = json.loads(captured.out.strip())
    assert log_entry["message"] == "test message"
    assert "timestamp" in log_entry
    assert "level" in log_entry


def test_get_logger_returns_named_logger():
    from app.core.logging import get_logger

    logger = get_logger("custom.module")
    assert logger.name == "custom.module"
    assert isinstance(logger, logging.Logger)
