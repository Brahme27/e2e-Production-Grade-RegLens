"""Structured logging.

Locally logs are pretty and coloured; in containers (``log_json=True``) every line
is one JSON object so tools like CloudWatch or Grafana Loki can search by field.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Configure structlog + stdlib logging once at program start."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        # no fixed file: each logger resolves sys.stdout when created, so redirected
        # or replaced streams (tests, notebooks) are always respected
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a logger tagged with the module name."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(module=name)
    return logger
