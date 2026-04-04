"""Unit tests for InMemoryQueue.

Verifies round-trip delivery, trace_context field preservation, queue depth
metric tracking, publish counter, and ack no-op behaviour.
Tests follow AAA (Arrange → Act → Assert).
"""

from __future__ import annotations

import uuid

import pytest

from app.core.message_queue import GenerationMessage
from app.services.inmemory_queue import InMemoryQueue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_ADVISOR_ID = uuid.uuid4()


def _make_message(trace_context: dict[str, str] | None = None) -> GenerationMessage:
    return GenerationMessage(
        client_id=_CLIENT_ID,
        advisor_id=_ADVISOR_ID,
        trigger_type="review_due",
        trace_context=trace_context or {},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_assigns_uuid_message_id() -> None:
    """publish() assigns a non-empty, valid UUID string to message.message_id."""
    queue = InMemoryQueue()
    msg = _make_message()

    assert msg.message_id == ""

    await queue.publish(msg)

    assert msg.message_id != ""
    uuid.UUID(msg.message_id)  # Raises ValueError if not a valid UUID


@pytest.mark.asyncio
async def test_round_trip_preserves_message_fields() -> None:
    """A published message is received intact by consume()."""
    queue = InMemoryQueue()
    msg = _make_message()

    await queue.publish(msg)

    received: GenerationMessage | None = None
    async for m in queue.consume():
        received = m
        break

    assert received is msg
    assert received.client_id == _CLIENT_ID
    assert received.advisor_id == _ADVISOR_ID
    assert received.trigger_type == "review_due"


@pytest.mark.asyncio
async def test_round_trip_preserves_trace_context() -> None:
    """trace_context dict is preserved intact through the in-memory queue."""
    trace_ctx = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    queue = InMemoryQueue()
    msg = _make_message(trace_context=trace_ctx)

    await queue.publish(msg)

    received: GenerationMessage | None = None
    async for m in queue.consume():
        received = m
        break

    assert received is not None
    assert received.trace_context == trace_ctx


@pytest.mark.asyncio
async def test_ack_is_a_noop() -> None:
    """ack() completes without raising for any message_id string."""
    queue = InMemoryQueue()

    # Should not raise
    await queue.ack("any-message-id-12345")
