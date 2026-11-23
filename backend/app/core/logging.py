"""Structured JSON logging with secret redaction."""

from __future__ import annotations

import logging
import re
from typing import Any

import structlog

_SENSITIVE_KEYS = re.compile(
    r"(password|secret|token|authorization|cookie|api[_-]?key|mfa|otp|code_hash|credential)", re.I
)


def _redact(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict):
        if key != "event" and _SENSITIVE_KEYS.search(key):
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )
