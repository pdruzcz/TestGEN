import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.core.config import get_settings


def setup_logging() -> logging.Logger:
    settings = get_settings()

    logger = logging.getLogger("testgen")
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "service",
        },
        static_fields={
            "app": settings.app_name,
            "env": settings.app_env,
        },
    )

    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)

    return logger


def get_logger(name: str = "testgen") -> logging.Logger:
    return logging.getLogger(name)
