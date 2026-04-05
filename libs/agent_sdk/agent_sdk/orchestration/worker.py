"""Generic async queue consumer base class.

Every autonomous agent that processes messages from a queue should subclass
``BaseQueueWorker`` and implement ``_handle()``.  The base class owns:

- Start / stop lifecycle (asyncio task management).
- OpenTelemetry span creation and W3C trace context propagation per message.
- Per-message error isolation — a single failure never crashes the loop.
- An ``_on_failure()`` hook for dead-letter, alerting, or metric recording.

The worker deliberately has no telemetry calls built-in.  Subclasses and the
host process add observability at their own boundary.

Usage::

    from agent_sdk.orchestration.worker import BaseQueueWorker
    from agent_sdk.core.message_queue import GenerationMessage
    from agent_sdk.core.session import IAsyncSession

    class MyWorker(BaseQueueWorker):
        async def _handle(self, message: GenerationMessage, session: IAsyncSession) -> None:
            # domain logic here
            ...
"""

from __future__ import annotations

import asyncio
import contextlib
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from agent_sdk.core.message_queue import GenerationMessage, MessageQueue
from agent_sdk.core.session import IAsyncSession, ISessionFactory

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)
_tracer = trace.get_tracer(__name__)


class BaseQueueWorker(ABC):
    """Abstract consumer loop for queue-backed agent pipelines.

    Subclasses implement ``_handle()`` with domain logic.  The base class
    manages task lifecycle, trace propagation, and per-message error isolation.

    Args:
        queue: Queue implementation from which messages are consumed.
        session_factory: Callable that returns an async-context-manager
            yielding an ``IAsyncSession``.  A fresh session is opened per
            message so that a failed session never pollutes the next one.
    """

    def __init__(
        self,
        queue: MessageQueue,
        session_factory: ISessionFactory,
    ) -> None:
        self._queue = queue
        self._session_factory = session_factory
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._log = structlog.get_logger(self.__class__.__module__)

    async def start(self) -> None:
        """Launch the consumer loop as a background asyncio task.

        Idempotent — calling start on an already-running worker is a no-op.
        """
        if self._running:
            return
        self._running = True
        worker_name = f"{self.__class__.__name__}-worker"
        self._task = asyncio.create_task(self._consume_loop(), name=worker_name)
        self._log.info("queue_worker_started", worker=self.__class__.__name__)

    async def stop(self) -> None:
        """Cancel the consumer loop and wait for it to exit cleanly.

        Safe to call even if the worker was never started.
        """
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._log.info("queue_worker_stopped", worker=self.__class__.__name__)

    @abstractmethod
    async def _handle(
        self,
        message: GenerationMessage,
        session: IAsyncSession,
    ) -> None:
        """Process one message using the provided async DB session.

        Raising any exception from this method will trigger ``_on_failure()``
        and then continue the loop — messages are never automatically re-queued.

        Args:
            message: The work item consumed from the queue.
            session: An active async session scoped to this single message.
                Commit or rollback as needed; the session is closed when this
                method returns.
        """
        ...

    async def _on_failure(
        self,
        message: GenerationMessage,
        error: Exception,
    ) -> None:
        """React to a per-message processing failure.

        Default implementation logs the error and returns.  Override to
        persist to a dead-letter table, emit a metric, or send an alert.

        Subclasses that need a DB session can open one via
        ``self._session_factory()``.

        Args:
            message: The message that caused the failure.
            error: The exception raised by ``_handle()``.
        """
        self._log.error(
            "queue_worker_message_failed",
            client_id=str(message.client_id),
            message_id=message.message_id,
            trigger_type=message.trigger_type,
            error=str(error),
            worker=self.__class__.__name__,
        )

    async def _consume_loop(self) -> None:
        """Inner loop — drain the queue and dispatch each message.

        Runs until ``_running`` is set to ``False`` (via ``stop()``) or the
        consumer generator is exhausted.  Individual message failures do not
        break the loop.
        """
        async for message in self._queue.consume():
            if not self._running:
                break

            log = self._log.bind(
                client_id=str(message.client_id),
                message_id=message.message_id,
                trigger_type=message.trigger_type,
            )
            log.info("queue_worker_processing")

            remote_ctx = TraceContextTextMapPropagator().extract(message.trace_context)
            with _tracer.start_as_current_span(
                f"{self.__class__.__name__}.process",
                context=remote_ctx,
            ) as span:
                span.set_attribute("client_id", str(message.client_id))
                span.set_attribute("trigger_type", message.trigger_type)

                try:
                    async with self._session_factory() as session:
                        await self._handle(message, session)

                    await self._queue.ack(message.message_id)
                    log.info("queue_worker_success")

                except Exception as exc:
                    log.error(
                        "queue_worker_failed",
                        error=str(exc),
                        exc_info=True,
                    )
                    try:
                        await self._on_failure(message, exc)
                    except Exception as fail_exc:
                        log.error(
                            "queue_worker_failure_handler_failed",
                            error=str(fail_exc),
                            exc_info=True,
                        )
                    # Always continue — never crash the loop on a per-message error.
