"""Scheduler trigger endpoint.

Exposes ``POST /scheduler/trigger`` so that the daily generation job can
be initiated by an external caller (e.g. AWS EventBridge, GCP Cloud
Scheduler, cron container) without embedding APScheduler in the process.

For local development APScheduler calls the same ``SchedulerService``
directly, so this endpoint and APScheduler are complementary, not
mutually exclusive.

Security: the endpoint is protected by a shared-secret header
``X-Scheduler-Secret`` validated against ``settings.SCHEDULER_SECRET``.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.services.scheduler import create_scheduler_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class TriggerResponse(BaseModel):
    """Response body for the trigger endpoint."""

    messages_published: int


@router.post(
    "/trigger",
    response_model=TriggerResponse,
    status_code=status.HTTP_200_OK,
    summary="Manually trigger the daily generation job",
)
async def trigger_scheduler(
    x_scheduler_secret: str = Header(..., alias="X-Scheduler-Secret"),
) -> TriggerResponse:
    """Fan out generation messages for all eligible clients.

    Validates the shared secret, then delegates to ``SchedulerService``
    which publishes one ``GenerationMessage`` per eligible client.

    Returns:
        TriggerResponse containing the count of messages published.

    Raises:
        403: If the ``X-Scheduler-Secret`` header is missing or incorrect.
    """
    if x_scheduler_secret != settings.SCHEDULER_SECRET:
        logger.warning("scheduler_trigger_unauthorized")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid scheduler secret.",
        )

    log = logger.bind(source="http_trigger")
    log.info("scheduler_trigger_received")

    svc = create_scheduler_service()
    published = await svc.publish_pending_generations()

    log.info("scheduler_trigger_complete", messages_published=published)
    return TriggerResponse(messages_published=published)
