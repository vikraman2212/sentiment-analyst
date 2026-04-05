"""Generic scheduler fan-out publisher base class.

Every scheduler job that enqueues work for downstream agents should subclass
``BaseSchedulerPublisher`` and implement ``_get_messages()``.  The base
class owns:

- Session lifecycle (one session per scheduler run via ``ISessionFactory``).
- Trace context injection into each outbound ``GenerationMessage``.
- Structured logging of publish counts and per-item details.
- Error isolation per message — a single publish failure does not abort
  the full fan-out; it is logged and skipped.

The publisher deliberately has no telemetry calls built-in.  Subclasses add
observability (e.g., Prometheus counters, OTEL spans) at their boundary.

Usage::

    from agent_sdk.orchestration.scheduler import BaseSchedulerPublisher
    from agent_sdk.core.message_queue import GenerationMessage
    from agent_sdk.core.session import IAsyncSession

    class DailyReviewPublisher(BaseSchedulerPublisher):
        async def _get_messages(self, session: IAsyncSession) -> list[GenerationMessage]:
            # query advisor/client data and build message list
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import structlog
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from agent_sdk.core.message_queue import GenerationMessage, MessageQueue
from agent_sdk.core.session import IAsyncSession, ISessionFactory

logger = structlog.get_logger(__name__)


class BaseSchedulerPublisher(ABC):
    """Abstract fan-out publisher for scheduler-driven work distribution.

    Subclasses implement ``_get_messages()`` to return the list of work
    items for a given run.  The base class handles session management,
    trace injection, and message publishing.

    Args:
        queue: Queue implementation to which messages are published.
        session_factory: Callable that returns an async-context-manager
            yielding an ``IAsyncSession`` for reading eligible work items.
    """

    def __init__(
        self,
        queue: MessageQueue,
        session_factory: ISessionFactory,
    ) -> None:
        self._queue = queue
        self._session_factory = session_factory
        self._log = structlog.get_logger(self.__class__.__module__)

    @abstractmethod
    async def _get_messages(self, session: IAsyncSession) -> list[GenerationMessage]:
        """Return the work items to publish for this scheduler run.

        This method is called inside an active session context.  Fetch
        eligible advisors, clients, or any other domain data here and
        return one ``GenerationMessage`` per unit of work.

        Args:
            session: Active async DB session for read-only queries.

        Returns:
            List of ``GenerationMessage`` objects to enqueue.  Returning
            an empty list is valid and results in a no-op run.
        """
        ...

    async def publish_all(self) -> int:
        """Open a session, fetch messages, inject trace context, publish all.

        Each message is published individually.  A failure on any single
        message is logged and skipped so that one bad item does not abort
        the remaining fan-out.

        Returns:
            Total number of ``GenerationMessage`` objects successfully published.
        """
        total_published = 0
        log = self._log.bind(publisher=self.__class__.__name__)
        log.info("scheduler_publish_started")

        try:
            async with self._session_factory() as session:
                messages = await self._get_messages(session)

            if not messages:
                log.info("scheduler_publish_no_messages")
                return 0

            for message in messages:
                try:
                    TraceContextTextMapPropagator().inject(message.trace_context)
                    await self._queue.publish(message)
                    total_published += 1
                    log.info(
                        "scheduler_message_published",
                        client_id=str(message.client_id),
                        advisor_id=str(message.advisor_id),
                        trigger_type=message.trigger_type,
                    )
                except Exception as exc:
                    log.error(
                        "scheduler_message_publish_failed",
                        client_id=str(message.client_id),
                        error=str(exc),
                        exc_info=True,
                    )

            log.info(
                "scheduler_publish_complete",
                total_published=total_published,
                total_attempted=len(messages),
            )
            return total_published

        except Exception as exc:
            log.error(
                "scheduler_publish_session_failed",
                error=str(exc),
                exc_info=True,
            )
            raise
