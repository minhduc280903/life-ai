"""Structured JSON logging with correlation ID support."""

import logging
import sys
from contextvars import ContextVar
from typing import Any
from uuid import UUID

import structlog

from app.core.config import get_settings

# Context variable for run_id correlation across async operations
run_id_context: ContextVar[str | None] = ContextVar("run_id", default=None)


def add_run_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add run_id from context to log entries."""
    run_id = run_id_context.get()
    if run_id:
        event_dict["run_id"] = run_id
    return event_dict


def setup_logging() -> None:
    """Configure structured logging based on settings."""
    settings = get_settings()

    # Determine processors based on log format
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_run_id,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def set_run_context(run_id: UUID | str) -> None:
    """Set the run_id context for log correlation."""
    run_id_context.set(str(run_id))


def clear_run_context() -> None:
    """Clear the run_id context."""
    run_id_context.set(None)
