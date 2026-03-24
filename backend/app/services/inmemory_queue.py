"""In-memory message queue implementation.

Uses ``asyncio.Queue`` as the backing store.  Suitable for local
development and testing — zero infrastructure required.  Not durable
across process restarts.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import structlog

from app.core.message_queue import GenerationMessage, MessageQueue
from app.core.telemetry import record_queue_publish, set_inmemory_queue_depth

logger = structlog.get_logger(__name__)


class InMemoryQueue:
    """``MessageQueue`` implementation backed by ``asyncio.Queue``.

    ``message_id`` is assigned as a random UUID string on publish.
    ``ack()`` is a no-op because in-memory delivery is inherently
    at-most-once — messages are removed from the queue on delivery.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[GenerationMessage] = asyncio.Queue()

    async def publish(self, message: GenerationMessage) -> None:
        """Enqueue a generation message, assigning a fresh message_id."""
        message.message_id = str(uuid.uuid4())
        log = logger.bind(
            client_id=str(message.client_id),
            message_id=message.message_id,
        )
        log.info("inmemory_queue_publish")
        await self._queue.put(message)
        record_queue_publish("inmemory")
        set_inmemory_queue_depth(self._queue.qsize())

    async def consume(self) -> AsyncIterator[GenerationMessage]:
        """Yield messages indefinitely, blocking when the queue is empty."""
        while True:
            message = await self._queue.get()
            set_inmemory_queue_depth(self._queue.qsize())
            logger.info(
                "inmemory_queue_consume",
                client_id=str(message.client_id),
                message_id=message.message_id,
            )
            yield message

    async def ack(self, message_id: str) -> None:
        """No-op for the in-memory backend — delivery is already consumed."""
        logger.debug("inmemory_queue_ack", message_id=message_id)


# Satisfy the structural Protocol check at import time.
_: MessageQueue = InMemoryQueue()  # type: ignore[assignment]
