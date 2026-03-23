"""Unit tests for RedisStreamQueue.

All Redis operations are mocked so no running Redis instance is required.
Verifies trace context serialisation on publish, reconstruction on consume,
metric recording, and ack invocation.
Tests follow AAA (Arrange → Act → Assert).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.message_queue import GenerationMessage
from app.services.redis_queue import _GROUP_NAME, _STREAM_KEY, RedisStreamQueue
from tests.services.conftest import get_metric_value

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_ADVISOR_ID = uuid.uuid4()
_REDIS_URL = "redis://localhost:6379"


def _make_message(trace_context: dict[str, str] | None = None) -> GenerationMessage:
    return GenerationMessage(
        client_id=_CLIENT_ID,
        advisor_id=_ADVISOR_ID,
        trigger_type="review_due",
        trace_context=trace_context or {},
    )


# ---------------------------------------------------------------------------
# publish() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_writes_traceparent_to_stream() -> None:
    """traceparent from message.trace_context is added to the Redis stream entry."""
    fake_entry_id = "1234-0"
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value=fake_entry_id)

    queue = RedisStreamQueue(redis_url=_REDIS_URL)
    msg = _make_message(trace_context={"traceparent": "00-aabbcc-ddeeff-01"})

    with patch("app.services.redis_queue.aioredis.from_url", return_value=mock_redis):
        await queue.publish(msg)

    payload = mock_redis.xadd.call_args.args[1]
    assert payload["traceparent"] == "00-aabbcc-ddeeff-01"
    assert msg.message_id == fake_entry_id


@pytest.mark.asyncio
async def test_publish_without_trace_context_omits_trace_fields() -> None:
    """When trace_context is empty, no traceparent or tracestate key appears in the stream."""
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="0-1")

    queue = RedisStreamQueue(redis_url=_REDIS_URL)

    with patch("app.services.redis_queue.aioredis.from_url", return_value=mock_redis):
        await queue.publish(_make_message())

    payload = mock_redis.xadd.call_args.args[1]
    assert "traceparent" not in payload
    assert "tracestate" not in payload


@pytest.mark.asyncio
async def test_publish_writes_core_fields_to_stream() -> None:
    """client_id, advisor_id, and trigger_type are always written to the stream entry."""
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="0-1")

    queue = RedisStreamQueue(redis_url=_REDIS_URL)

    with patch("app.services.redis_queue.aioredis.from_url", return_value=mock_redis):
        await queue.publish(_make_message())

    payload = mock_redis.xadd.call_args.args[1]
    assert payload["client_id"] == str(_CLIENT_ID)
    assert payload["advisor_id"] == str(_ADVISOR_ID)
    assert payload["trigger_type"] == "review_due"


@pytest.mark.asyncio
async def test_publish_increments_redis_queue_metric() -> None:
    """publish() increments the redis publish counter by one."""
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="0-1")
    before = get_metric_value("sentiment_queue_messages_published_total", {"backend": "redis"})

    with patch("app.services.redis_queue.aioredis.from_url", return_value=mock_redis):
        queue = RedisStreamQueue(redis_url=_REDIS_URL)
        await queue.publish(_make_message())

    assert (
        get_metric_value("sentiment_queue_messages_published_total", {"backend": "redis"})
        == before + 1
    )


# ---------------------------------------------------------------------------
# consume() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consume_reconstructs_trace_context_from_stream_fields() -> None:
    """trace_context is rebuilt from traceparent and tracestate stream fields on consume."""
    entry_id = "1234-0"
    stream_fields = {
        "client_id": str(_CLIENT_ID),
        "advisor_id": str(_ADVISOR_ID),
        "trigger_type": "review_due",
        "traceparent": "00-abc123-def456-01",
        "tracestate": "vendor=value",
    }
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    mock_redis.xreadgroup = AsyncMock(
        return_value=[[_STREAM_KEY, [(entry_id, stream_fields)]]]
    )

    with patch("app.services.redis_queue.aioredis.from_url", return_value=mock_redis):
        queue = RedisStreamQueue(redis_url=_REDIS_URL)
        received: GenerationMessage | None = None
        async for msg in queue.consume():
            received = msg
            break

    assert received is not None
    assert received.trace_context == {
        "traceparent": "00-abc123-def456-01",
        "tracestate": "vendor=value",
    }
    assert received.client_id == _CLIENT_ID
    assert received.advisor_id == _ADVISOR_ID
    assert received.message_id == entry_id


@pytest.mark.asyncio
async def test_consume_omits_trace_context_when_fields_absent() -> None:
    """When traceparent/tracestate are absent from the stream, trace_context is empty."""
    entry_id = "9999-0"
    stream_fields = {
        "client_id": str(_CLIENT_ID),
        "advisor_id": str(_ADVISOR_ID),
        "trigger_type": "review_due",
    }
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    mock_redis.xreadgroup = AsyncMock(
        return_value=[[_STREAM_KEY, [(entry_id, stream_fields)]]]
    )

    with patch("app.services.redis_queue.aioredis.from_url", return_value=mock_redis):
        queue = RedisStreamQueue(redis_url=_REDIS_URL)
        received: GenerationMessage | None = None
        async for msg in queue.consume():
            received = msg
            break

    assert received is not None
    assert received.trace_context == {}


@pytest.mark.asyncio
async def test_consume_skips_empty_poll_and_yields_next_message() -> None:
    """When xreadgroup returns no entries the loop continues without yielding."""
    entry_id = "5555-0"
    stream_fields = {
        "client_id": str(_CLIENT_ID),
        "advisor_id": str(_ADVISOR_ID),
        "trigger_type": "review_due",
    }
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    mock_redis.xreadgroup = AsyncMock(
        side_effect=[
            [],  # First poll: nothing
            [[_STREAM_KEY, [(entry_id, stream_fields)]]],  # Second poll: message
        ]
    )

    with patch("app.services.redis_queue.aioredis.from_url", return_value=mock_redis):
        queue = RedisStreamQueue(redis_url=_REDIS_URL)
        received: GenerationMessage | None = None
        async for msg in queue.consume():
            received = msg
            break

    assert received is not None
    assert received.message_id == entry_id


# ---------------------------------------------------------------------------
# ack() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ack_calls_xack_with_correct_keys() -> None:
    """ack() calls xack with the stream key, group name, and message_id."""
    mock_redis = AsyncMock()
    mock_redis.xack = AsyncMock()

    queue = RedisStreamQueue(redis_url=_REDIS_URL)

    with patch("app.services.redis_queue.aioredis.from_url", return_value=mock_redis):
        await queue.ack("1234-0")

    mock_redis.xack.assert_called_once_with(_STREAM_KEY, _GROUP_NAME, "1234-0")
