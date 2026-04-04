"""Queue dependency factory.

Returns the correct ``MessageQueue`` implementation based on
``settings.QUEUE_BACKEND``.  Concrete adapters now come from
``agent_sdk.providers.queue`` so that autonomous agents can share the
exact same queue implementation without importing ``app.*``.

Usage::

    from app.dependencies.queue import get_queue

    queue = get_queue()
    await queue.publish(message)
"""

from __future__ import annotations

import structlog
from agent_sdk.core.message_queue import MessageQueue

from app.core.config import settings

logger = structlog.get_logger(__name__)

_queue_instance: MessageQueue | None = None


def get_queue() -> MessageQueue:
    """Return the singleton queue instance for the configured backend.

    The instance is created once and reused for the process lifetime so
    the worker consumer loop and the scheduler publisher share the same
    underlying queue object.

    Returns:
        MessageQueue implementation for the configured backend.

    Raises:
        ValueError: If ``QUEUE_BACKEND`` is set to an unsupported value.
    """
    global _queue_instance

    if _queue_instance is not None:
        return _queue_instance

    backend = settings.QUEUE_BACKEND.lower()
    logger.info("queue_factory_init", backend=backend)

    if backend == "inmemory":
        from agent_sdk.providers.queue.inmemory import InMemoryQueue

        _queue_instance = InMemoryQueue()

    elif backend == "redis":
        from agent_sdk.providers.queue.redis import RedisStreamQueue

        _queue_instance = RedisStreamQueue(redis_url=settings.REDIS_URL)

    else:
        raise ValueError(
            f"Unsupported QUEUE_BACKEND '{settings.QUEUE_BACKEND}'. "
            "Valid values: 'inmemory', 'redis'."
        )

    return _queue_instance
