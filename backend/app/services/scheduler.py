"""Scheduler publisher service.

Responsible for the fan-out step of the daily generation pipeline:

1. Open a database session.
2. Iterate over every advisor via ``AdvisorRepository.list_all()``.
3. For each advisor, retrieve eligible clients via
   ``ContextAssemblyService.list_needing_review(advisor_id)``.
4. Publish one ``GenerationMessage`` per eligible client.
5. Return immediately — actual generation is performed by the worker consumer.

This function is called by:
- APScheduler's daily cron job (local / on-prem).
- The ``POST /api/v1/scheduler/trigger`` endpoint (EventBridge / cloud).
"""

from __future__ import annotations

from time import perf_counter

import structlog

from app.core.message_queue import GenerationMessage, MessageQueue
from app.core.telemetry import record_scheduler_run
from app.db.session import AsyncSessionLocal
from app.dependencies.queue import get_queue
from app.repositories.advisor import AdvisorRepository
from app.services.context_assembly import ContextAssemblyService

logger = structlog.get_logger(__name__)


class SchedulerService:
    """Fan-out publisher: list eligible clients and enqueue generation work.

    Accepts an injected ``MessageQueue`` for testing; falls back to the
    factory from ``app/dependencies/queue.py`` when not provided.
    """

    def __init__(self, queue: MessageQueue | None = None) -> None:
        self._queue = queue or get_queue()

    async def publish_pending_generations(self) -> int:
        """Query eligible clients across all advisors and publish messages.

        Opens its own ``AsyncSession`` so it can be called from both the
        APScheduler job function (outside a request context) and the trigger
        HTTP endpoint.

        Returns:
            The total number of ``GenerationMessage`` objects published.
        """
        started_at = perf_counter()
        status = "error"
        total_published = 0
        log = logger.bind(job="publish_pending_generations")
        log.info("scheduler_publish_started")

        try:
            async with AsyncSessionLocal() as db:
                advisor_repo = AdvisorRepository(db)
                advisors = await advisor_repo.list_all()

                if not advisors:
                    status = "success"
                    log.info("scheduler_publish_no_advisors")
                    return 0

                for advisor in advisors:
                    context_svc = ContextAssemblyService(db)
                    try:
                        contexts = await context_svc.list_needing_review(advisor.id)
                    except Exception as exc:
                        log.error(
                            "scheduler_publish_advisor_failed",
                            advisor_id=str(advisor.id),
                            error=str(exc),
                            exc_info=True,
                        )
                        continue

                    for ctx in contexts:
                        message = GenerationMessage(
                            client_id=ctx.client_id,
                            advisor_id=advisor.id,
                            trigger_type="review_due",
                        )
                        await self._queue.publish(message)
                        total_published += 1
                        log.info(
                            "scheduler_message_published",
                            client_id=str(ctx.client_id),
                            advisor_id=str(advisor.id),
                        )

            status = "success"
            log.info("scheduler_publish_complete", total_published=total_published)
            return total_published
        finally:
            record_scheduler_run(
                status=status,
                duration_seconds=perf_counter() - started_at,
                published_count=total_published,
            )
