"""Async LLM audit logging service.

Provides a fire-and-forget utility for writing LLM transaction metadata
(pipeline, model, token counts, latency, prompt, response) to the
``llm-audits`` OpenSearch index after every Ollama call.

Callers should use ``asyncio.create_task`` so that audit writes never
block the primary request path::

    import asyncio
    asyncio.create_task(llm_audit_logger.log(event))

Logging failures are swallowed and reported as structlog warnings only.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone

import structlog

from app.core.opensearch import get_opensearch_client

logger = structlog.get_logger(__name__)

_LLM_AUDITS_INDEX = "llm-audits"


@dataclasses.dataclass
class LLMAuditEvent:
    """Serialisable record of a single LLM call."""

    pipeline: str           # "extraction" | "generation"
    client_id: str          # str representation of UUID
    model: str
    prompt: str
    response: str
    status: str             # "success" | "error"
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error: str | None = None


class LLMAuditLogger:
    """Writes LLMAuditEvent documents to OpenSearch asynchronously.

    All exceptions from the OpenSearch client are caught and logged as
    warnings — ``log()`` will never propagate an exception to its caller.
    """

    async def log(self, event: LLMAuditEvent) -> None:
        """Index a single audit event.

        Args:
            event: Fully populated LLMAuditEvent instance.
        """
        try:
            client = get_opensearch_client()
            await client.index(
                index=_LLM_AUDITS_INDEX,
                body=dataclasses.asdict(event),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "llm_audit_failed",
                pipeline=event.pipeline,
                client_id=event.client_id,
                error=str(exc),
            )


llm_audit_logger = LLMAuditLogger()


def make_audit_event(
    *,
    pipeline: str,
    client_id: uuid.UUID,
    model: str,
    prompt: str,
    response: str,
    status: str,
    latency_ms: float,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    error: str | None = None,
) -> LLMAuditEvent:
    """Convenience constructor that converts UUID to str.

    Args:
        pipeline: Name of the pipeline emitting the event.
        client_id: Client UUID.
        model: Ollama model name used.
        prompt: Full prompt sent to the model.
        response: Raw model response string.
        status: ``"success"`` or ``"error"``.
        latency_ms: End-to-end Ollama call latency in milliseconds.
        prompt_tokens: Number of prompt tokens evaluated (from Ollama body).
        completion_tokens: Number of completion tokens generated (from Ollama body).
        error: Optional error message for failed calls.

    Returns:
        A populated LLMAuditEvent ready to pass to ``llm_audit_logger.log()``.
    """
    return LLMAuditEvent(
        pipeline=pipeline,
        client_id=str(client_id),
        model=model,
        prompt=prompt,
        response=response,
        status=status,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        error=error,
    )
