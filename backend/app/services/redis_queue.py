"""Redis Streams message queue implementation.

Uses Redis Streams with a consumer group for at-least-once delivery and
proper ack semantics.  Redis is available as a managed service on every
major cloud (AWS ElastiCache, GCP Memorystore, Azure Cache for Redis),
making this implementation cloud-agnostic.

Stream key: ``sentiment:generation``
Consumer group: ``generation-worker``
Consumer name: ``worker-0``

Failed messages (nack / unprocessed) are left in the pending-entries list
(PEL) for external dead-letter handling — the worker logs and continues
rather than stopping the consumer loop.
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

import redis.asyncio as aioredis
import structlog

from app.core.config import settings
from app.core.message_queue import GenerationMessage, MessageQueue
from app.core.telemetry import record_queue_publish

logger = structlog.get_logger(__name__)

_STREAM_KEY = "sentiment:generation"
_GROUP_NAME = "generation-worker"
_CONSUMER_NAME = "worker-0"
_BLOCK_MS = 5_000  # Block for 5 s waiting for new entries
_BATCH_SIZE = 1  # Read one message at a time for simplicity


class RedisStreamQueue:
    """``MessageQueue`` implementation backed by Redis Streams.

    A consumer group is created (or confirmed) on first ``consume()`` call
    so the instance is safe to publish to without calling ``consume()`` first.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.REDIS_URL
        self._client: aioredis.Redis | None = None  # type: ignore[type-arg]

    async def _get_client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        if self._client is None:
            self._client = aioredis.from_url(
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
        """Append a generation message to the Redis stream."""
        client = await self._get_client()
        payload: dict[str, str | int | float] = {
            "client_id": str(message.client_id),
            "advisor_id": str(message.advisor_id),
            "trigger_type": message.trigger_type,
        }
        entry_id: str = await client.xadd(_STREAM_KEY, payload)  # type: ignore[assignment,arg-type]
        message.message_id = entry_id
        record_queue_publish("redis")
        logger.info(
            "redis_stream_publish",
            client_id=str(message.client_id),
            message_id=entry_id,
        )

    async def consume(self) -> AsyncIterator[GenerationMessage]:
        """Yield messages from the consumer group, blocking between polls."""
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
                    msg = GenerationMessage(
                        client_id=uuid.UUID(fields["client_id"]),
                        advisor_id=uuid.UUID(fields["advisor_id"]),
                        trigger_type=fields["trigger_type"],
                        message_id=entry_id,
                    )
                    logger.info(
                        "redis_stream_consume",
                        client_id=str(msg.client_id),
                        message_id=entry_id,
                    )
                    yield msg

    async def ack(self, message_id: str) -> None:
        """Acknowledge successful processing so the PEL entry is removed."""
        client = await self._get_client()
        await client.xack(_STREAM_KEY, _GROUP_NAME, message_id)
        logger.debug("redis_stream_ack", message_id=message_id)


# Satisfy the structural Protocol check at import time.
_: MessageQueue = RedisStreamQueue()  # type: ignore[assignment]
