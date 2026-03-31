"""Structured JSON logging configuration with request ID tracking."""

import logging
import uuid
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

# Context variable for request ID tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    """Inject request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")  # type: ignore[attr-defined]
        return True


def generate_request_id() -> str:
    return uuid.uuid4().hex[:12]


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """Configure root logger with optional JSON format and request ID filter."""
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler()

    if json_format:
        formatter = JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(request_id)s] %(name)s %(levelname)s %(message)s"
        )

    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)
