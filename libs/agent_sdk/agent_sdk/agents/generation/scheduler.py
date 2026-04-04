"""Scheduler service — fan-out publisher for the generation agent.

Subclasses ``BaseSchedulerPublisher`` from the SDK.  The base class handles
session lifecycle, trace-context injection, and per-message publish error
isolation.  This class contributes only the generation-specific wiring:

- ``_get_messages()`` — delegates to the injected ``IClientSource`` to
  obtain the list of eligible (client_id, advisor_id) pairs and converts
  them into ``GenerationMessage`` objects.
- ``publish_pending_generations()`` — public wrapper that calls
  ``publish_all()`` and invokes the optional telemetry callback.

Called by:
- APScheduler's daily cron job (local / on-prem).
- The ``POST /api/v1/scheduler/trigger`` endpoint (EventBridge / cloud).
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

import structlog

from agent_sdk.agents.generation.ports import IClientSource
from agent_sdk.core.message_queue import GenerationMessage, MessageQueue
from agent_sdk.core.session import IAsyncSession, ISessionFactory
from agent_sdk.orchestration.scheduler import BaseSchedulerPublisher

logger = structlog.get_logger(__name__)


class SchedulerService(BaseSchedulerPublisher):
    """Fan-out publisher: list eligible clients and enqueue generation work.

    The actual eligibility query is fully delegated to the injected
    ``IClientSource`` so the scheduler contains zero SQL and can be tested
    without a database.

    Args:
        queue: Queue to which ``GenerationMessage`` objects are published.
        session_factory: Async-context-manager factory yielding a session
            compatible with ``IAsyncSession``.
        client_source: Provides eligible (client_id, advisor_id) pairs.
        on_publish_complete: Optional callback invoked after each run with
            ``(status: str, count: int, duration_seconds: float)``.  Use
            for Prometheus counters without coupling the SDK to a metrics
            library.
    """

    def __init__(
        self,
        queue: MessageQueue,
        session_factory: ISessionFactory,
        client_source: IClientSource,
        on_publish_complete: Callable[[str, int, float], None] | None = None,
    ) -> None:
        super().__init__(queue=queue, session_factory=session_factory)
        self._client_source = client_source
        self._on_publish_complete = on_publish_complete

    async def _get_messages(
        self, session: IAsyncSession
    ) -> list[GenerationMessage]:
        """Delegate to ``IClientSource`` and build ``GenerationMessage`` objects.

        Args:
            session: Active async DB session for eligibility queries.

        Returns:
            One ``GenerationMessage`` per eligible (client_id, advisor_id) pair.
        """
        pairs = await self._client_source.get_eligible_clients(session)
        return [
            GenerationMessage(
                client_id=client_id,
                advisor_id=advisor_id,
                trigger_type="review_due",
            )
            for client_id, advisor_id in pairs
        ]

    async def publish_pending_generations(self) -> int:
        """Publish generation messages for all eligible clients.

        Wraps ``publish_all()`` with optional telemetry.  Maintains the
        public API so callers (``main.py``, the scheduler router) need no
        changes.

        Returns:
            Total number of ``GenerationMessage`` objects published.
        """
        started_at = perf_counter()
        status = "error"
        count = 0
        log = logger.bind(job="publish_pending_generations")
        log.info("scheduler_publish_started")

        try:
            count = await self.publish_all()
            status = "success"
            log.info("scheduler_publish_complete", total_published=count)
            return count
        except Exception as exc:
            log.error("scheduler_publish_failed", error=str(exc), exc_info=True)
            raise
        finally:
            if self._on_publish_complete:
                self._on_publish_complete(status, count, perf_counter() - started_at)
