"""Structured logging configuration using structlog.

Call ``configure_logging()`` once at application startup from ``app/main.py``.
All other modules obtain their logger via::

    import structlog
    logger = structlog.get_logger(__name__)
"""

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON-formatted structured output.

    Args:
        log_level: Minimum log level string (e.g. ``"INFO"``, ``"DEBUG"``).
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
    )
