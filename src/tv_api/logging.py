"""Centralized logging configuration for the PickleTV API."""

from __future__ import annotations

import logging
from logging.config import dictConfig

_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "tv_api": {"handlers": ["console"], "level": "INFO"},
        "tv_api.request": {"handlers": ["console"], "level": "INFO"},
    },
}


def configure_logging(level: str = "INFO") -> None:
    """Configure application-wide logging once."""

    config = _LOGGING_CONFIG.copy()
    config["root"] = {"level": level.upper(), "handlers": ["console"]}
    dictConfig(config)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a namespaced logger within the tv_api hierarchy."""

    full_name = f"tv_api.{name}" if name else "tv_api"
    return logging.getLogger(full_name)
