"""Scheduler service — backend wiring.

Re-exports the SDK's ``SchedulerService`` and provides a
``create_scheduler_service()`` factory that wires it with all
backend-specific dependencies (adaptors + telemetry).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from agent_sdk.agents.generation.scheduler import SchedulerService  # noqa: F401
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.generation.adaptors import EligibleClientSource
from app.core.telemetry import record_scheduler_run
from app.db.session import AsyncSessionLocal
from app.dependencies.queue import get_queue


@asynccontextmanager
async def _session_factory() -> AsyncGenerator[AsyncSession, None]:
    """Module-level session factory — patchable in tests."""
    async with AsyncSessionLocal() as session:
        yield session


def _on_publish_complete(status: str, count: int, duration_seconds: float) -> None:
    record_scheduler_run(
        status=status,
        duration_seconds=duration_seconds,
        published_count=count,
    )


def create_scheduler_service() -> SchedulerService:
    """Build a fully-wired ``SchedulerService`` for the backend runtime."""
    return SchedulerService(
        queue=get_queue(),
        session_factory=_session_factory,  # type: ignore[arg-type]
        client_source=EligibleClientSource(),
        on_publish_complete=_on_publish_complete,
    )


__all__ = ["SchedulerService", "create_scheduler_service"]
