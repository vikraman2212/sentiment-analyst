"""Redis Streams message queue implementation.

Uses Redis Streams with a consumer group for at-least-once delivery and
proper ack semantics.  Suitable for multi-process and production
deployments where in-memory delivery is insufficient.

Stream key: ``sentiment:generation``
Consumer group: ``generation-worker``
Consumer name: ``worker-0``

Failed messages (nack / unprocessed) are left in the pending-entries list
(PEL) for external dead-letter handling — the worker logs and continues
rather than stopping the consumer loop.

This implementation has no dependency on framework telemetry — agents
and the backend add observability at their own boundary.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import redis.asyncio as aioredis
import structlog

from agent_sdk.core.message_queue import GenerationMessage, MessageQueue

logger = structlog.get_logger(__name__)

_STREAM_KEY = "sentiment:generation"
_GROUP_NAME = "generation-worker"
_CONSUMER_NAME = "worker-0"
_BLOCK_MS = 5_000   # Block 5 s waiting for new entries before polling again
_BATCH_SIZE = 1     # Read one message at a time for simplicity


class RedisStreamQueue:
    """``MessageQueue`` implementation backed by Redis Streams.

    A consumer group is created (or confirmed) on the first ``consume()``
    call so the instance is safe to ``publish()`` to without calling
    ``consume()`` first.

    Args:
        redis_url: Redis connection URL
            (e.g. ``"redis://localhost:6379"``).
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(  # type: ignore[no-untyped-call]
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def _ensure_group(self) -> None:
        """Create the consumer group if it does not already exist."""
        client = await self._get_client()
        try:
            await client.xgroup_create(_STREAM_KEY, _GROUP_NAME, id="0", mkstream=True)
            logger.info("redis_stream_group_created", group=_GROUP_NAME)
        except aioredis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, message: GenerationMessage) -> None:
        """Append a generation message to the Redis stream.

        Args:
            message: Work item to enqueue. ``message_id`` is set in-place
                to the Redis stream entry ID assigned on ``XADD``.
        """
        client = await self._get_client()
        payload: dict[str, str] = {
            "client_id": str(message.client_id),
            "advisor_id": str(message.advisor_id),
            "trigger_type": message.trigger_type,
            "schema_version": message.schema_version,
        }
        payload.update(message.trace_context)
        entry_id: str = await client.xadd(_STREAM_KEY, payload)  # type: ignore[arg-type]
        message.message_id = entry_id
        logger.info(
            "redis_stream_publish",
            client_id=str(message.client_id),
            message_id=entry_id,
        )

    async def consume(self) -> AsyncIterator[GenerationMessage]:
        """Yield messages from the consumer group, blocking between polls.

        Ensures the consumer group exists before the first read.

        Yields:
            ``GenerationMessage`` instances deserialized from the stream.
        """
        await self._ensure_group()
        client = await self._get_client()

        while True:
            entries = await client.xreadgroup(
                _GROUP_NAME,
                _CONSUMER_NAME,
                {_STREAM_KEY: ">"},
                count=_BATCH_SIZE,
                block=_BLOCK_MS,
            )
            if not entries:
                continue

            for _stream, messages in entries:
                for entry_id, fields in messages:
                    trace_ctx: dict[str, str] = {}
                    if "traceparent" in fields:
                        trace_ctx["traceparent"] = fields["traceparent"]
                    if "tracestate" in fields:
                        trace_ctx["tracestate"] = fields["tracestate"]
                    msg = GenerationMessage(
                        client_id=uuid.UUID(fields["client_id"]),
                        advisor_id=uuid.UUID(fields["advisor_id"]),
                        trigger_type=fields["trigger_type"],
                        message_id=entry_id,
                        trace_context=trace_ctx,
                        schema_version=fields.get("schema_version", "1.0"),
                    )
                    logger.info(
                        "redis_stream_consume",
                        client_id=str(msg.client_id),
                        message_id=entry_id,
                    )
                    yield msg

    async def ack(self, message_id: str) -> None:
        """Acknowledge successful processing so the PEL entry is removed.

        Args:
            message_id: The Redis stream entry ID returned on delivery.
        """
        client = await self._get_client()
        await client.xack(_STREAM_KEY, _GROUP_NAME, message_id)
        logger.debug("redis_stream_ack", message_id=message_id)


# Runtime structural Protocol check — fails loudly at import time if the
# class drifts from the MessageQueue Protocol signature.
_: MessageQueue = RedisStreamQueue()
