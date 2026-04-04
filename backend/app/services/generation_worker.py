"""Generation worker — backend wiring.

Re-exports the SDK's ``GenerationWorker`` and provides a
``create_generation_worker()`` factory that wires it with all
backend-specific dependencies (adaptors + telemetry).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from agent_sdk.agents.generation.worker import GenerationWorker  # noqa: F401
from agent_sdk.core.message_queue import GenerationMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.generation.adaptors import ContextAssemblyAdaptor, MessageDraftAdaptor
from app.core.config import settings
from app.core.telemetry import record_llm_metrics, record_worker_run
from app.db.session import AsyncSessionLocal
from app.dependencies.llm import get_llm_provider
from app.dependencies.queue import get_queue
from app.repositories.generation_failure import GenerationFailureRepository

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def _session_factory() -> AsyncGenerator[AsyncSession, None]:
    """Module-level session factory — patchable in tests."""
    async with AsyncSessionLocal() as session:
        yield session


async def persist_generation_failure(
    message: GenerationMessage, error: Exception
) -> None:
    """Persist a failed generation message to the dead-letter table."""
    log = logger.bind(
        client_id=str(message.client_id),
        message_id=message.message_id,
    )
    try:
        async with AsyncSessionLocal() as db:
            repo = GenerationFailureRepository(db)
            await repo.create(
                client_id=message.client_id,
                trigger_type=message.trigger_type,
                message_id=message.message_id,
                error_detail=str(error),
            )
    except Exception as exc:
        log.error("persist_generation_failure_db_error", error=str(exc), exc_info=True)


def _on_llm_complete(
    model: str,
    status: str,
    duration_seconds: float,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> None:
    record_llm_metrics(
        pipeline="generation",
        model=model,
        status=status,
        duration_seconds=duration_seconds,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def create_generation_worker() -> GenerationWorker:
    """Build a fully-wired ``GenerationWorker`` for the backend runtime."""
    return GenerationWorker(
        queue=get_queue(),
        session_factory=_session_factory,  # type: ignore[arg-type]
        context_reader_factory=ContextAssemblyAdaptor,  # type: ignore[arg-type]
        draft_writer_factory=MessageDraftAdaptor,  # type: ignore[arg-type]
        provider=get_llm_provider(),
        generation_model=settings.OLLAMA_GENERATION_MODEL,
        system_prompt=settings.GENERATION_PROMPT_OVERRIDE or None,
        on_run_complete=record_worker_run,
        on_failure=persist_generation_failure,
        on_llm_complete=_on_llm_complete,
    )


__all__ = ["GenerationWorker", "create_generation_worker", "persist_generation_failure"]
