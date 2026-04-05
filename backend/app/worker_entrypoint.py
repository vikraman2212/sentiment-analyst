"""Standalone email-generation worker entrypoint.

Runs the GenerationWorker consumer loop as an isolated process,
independent of the FastAPI application.  Use this when deploying the
worker as its own Docker Compose service (``agents`` profile).

Usage::

    python -m app.worker_entrypoint
"""
from __future__ import annotations

import asyncio

import structlog

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.telemetry import configure_telemetry, shutdown_telemetry
from app.services.generation_worker import create_generation_worker

configure_logging(log_level=settings.LOG_LEVEL)
configure_telemetry()

logger = structlog.get_logger(__name__)


async def main() -> None:
    """Start the generation worker and block until cancelled."""
    logger.info("email_agent_starting")
    worker = create_generation_worker()
    await worker.start()
    logger.info("email_agent_started")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("email_agent_stopping")
        await worker.stop()
        shutdown_telemetry()
        logger.info("email_agent_stopped")


if __name__ == "__main__":
    asyncio.run(main())
