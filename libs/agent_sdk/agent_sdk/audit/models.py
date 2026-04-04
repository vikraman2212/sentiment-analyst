"""Audit event dataclass.

``LLMAuditEvent`` is the single structured record written by every
LLM call across extraction and generation pipelines.  It is
intentionally free of PII — client names, email addresses, and
financial amounts must never appear in these records.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime


@dataclasses.dataclass
class LLMAuditEvent:
    """Serialisable record of a single LLM call.

    Attributes:
        pipeline: Which pipeline produced this event — ``"extraction"``
            or ``"generation"``.
        client_id: String representation of the target client UUID.
        model: Model identifier passed to the provider (e.g. ``"llama3.2"``).
        prompt: Raw prompt submitted — must not contain PII.
        response: Raw model response text.
        status: Outcome — ``"success"`` or ``"error"``.
        latency_ms: Wall-clock latency of the LLM call in milliseconds.
        prompt_tokens: Tokens consumed by the prompt, if reported.
        completion_tokens: Tokens in the completion, if reported.
        timestamp: ISO-8601 UTC timestamp of the event.
        error: Error message when ``status="error"``, otherwise ``None``.
        trace_id: OpenTelemetry trace ID for correlated tracing, if available.
        span_id: OpenTelemetry span ID, if available.
    """

    pipeline: str
    client_id: str
    model: str
    prompt: str
    response: str
    status: str
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    error: str | None = None
    trace_id: str | None = None
    span_id: str | None = None


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
    trace_id: str | None = None,
    span_id: str | None = None,
) -> LLMAuditEvent:
    """Convenience constructor that converts ``UUID`` to ``str``.

    Args:
        pipeline: ``"extraction"`` or ``"generation"``.
        client_id: Target client UUID.
        model: Model identifier.
        prompt: Raw prompt — must not contain PII.
        response: Raw model response.
        status: ``"success"`` or ``"error"``.
        latency_ms: Call latency in milliseconds.
        prompt_tokens: Prompt token count from provider, or ``None``.
        completion_tokens: Completion token count from provider, or ``None``.
        error: Error description when ``status="error"``.
        trace_id: OpenTelemetry trace ID string.
        span_id: OpenTelemetry span ID string.

    Returns:
        Fully populated ``LLMAuditEvent``.
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
        trace_id=trace_id,
        span_id=span_id,
    )
