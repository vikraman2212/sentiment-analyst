"""Generation worker — asynchronous queue consumer.

Runs as a long-lived ``asyncio`` task started in the FastAPI lifespan.
For each ``GenerationMessage`` delivered by the queue it:

1. Opens a database session.
2. Calls ``GenerationService.generate(client_id, trigger_type)``.
3. Acks the message on success.
4. Logs the failure and continues on error — the message remains in
   the pending-entries list (PEL) for Redis Streams, or is simply
   dropped for the in-memory backend.  The worker never crashes the
   consumer loop on a per-message failure.
"""

from __future__ import annotations

import asyncio
from time import perf_counter

import structlog

from app.core.message_queue import MessageQueue
from app.core.telemetry import record_worker_run
from app.db.session import AsyncSessionLocal
from app.dependencies.queue import get_queue
from app.repositories.generation_failure import GenerationFailureRepository
from app.services.generation_service import GenerationService

logger = structlog.get_logger(__name__)


class GenerationWorker:
    """Consumer loop that drains the message queue and calls GenerationService.

    Accepts an injected ``MessageQueue`` for testing; falls back to the
    factory from ``app/dependencies/queue.py`` when not provided.
    """

    def __init__(self, queue: MessageQueue | None = None) -> None:
        self._queue = queue or get_queue()
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Launch the consumer loop as a background asyncio task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._consume_loop(), name="generation-worker")
        logger.info("generation_worker_started")

    async def stop(self) -> None:
        """Cancel the consumer loop and wait for it to exit cleanly."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("generation_worker_stopped")

    async def _consume_loop(self) -> None:
        """Inner loop: consume messages and dispatch to GenerationService."""
        async for message in self._queue.consume():
            if not self._running:
                break

            started_at = perf_counter()
            status = "error"
            log = logger.bind(
                client_id=str(message.client_id),
                message_id=message.message_id,
                trigger_type=message.trigger_type,
            )
            log.info("generation_worker_processing")

            try:
                async with AsyncSessionLocal() as db:
                    svc = GenerationService(db)
                    await svc.generate(message.client_id, message.trigger_type)

                await self._queue.ack(message.message_id)
                status = "success"
                log.info("generation_worker_success")

            except Exception as exc:
                log.error(
                    "generation_worker_failed",
                    error=str(exc),
                    exc_info=True,
                )
                # Persist to dead-letter table so failures are observable.
                try:
                    async with AsyncSessionLocal() as db:
                        failure_repo = GenerationFailureRepository(db)
                        failure = await failure_repo.create(
                            client_id=message.client_id,
                            trigger_type=message.trigger_type,
                            message_id=message.message_id,
                            error_detail=str(exc),
                        )
                        log.warning(
                            "generation_failure_persisted",
                            failure_id=str(failure.id),
                        )
                except Exception as persist_exc:
                    log.error(
                        "generation_failure_persist_error",
                        error=str(persist_exc),
                        exc_info=True,
                    )
                # Continue the loop — do not let a single failure crash the worker.
            finally:
                record_worker_run(
                    status=status,
                    duration_seconds=perf_counter() - started_at,
                )
