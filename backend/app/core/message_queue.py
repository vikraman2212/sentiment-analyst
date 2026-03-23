"""Message queue abstraction — shared types and protocol.

Defines a provider-agnostic interface so that the scheduler publisher and
the generation worker are decoupled from any specific queue backend
(in-memory asyncio.Queue, Redis Streams, SQS, etc.).

Concrete implementations live in ``app/services/``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol, runtime_checkable


@dataclass
class GenerationMessage:
    """A single unit of work enqueued by the scheduler publisher."""

    client_id: uuid.UUID
    advisor_id: uuid.UUID
    trigger_type: str
    message_id: str = ""  # Populated by the queue implementation on publish
    trace_context: dict[str, str] = field(default_factory=dict)  # W3C TraceContext carrier


@runtime_checkable
class MessageQueue(Protocol):
    """Structural interface every queue backend must satisfy.

    The protocol mirrors ``LLMProvider`` — callers depend on this
    abstraction; concrete implementations are injected via the factory
    in ``app/dependencies/queue.py``.
    """

    async def publish(self, message: GenerationMessage) -> None:
        """Enqueue a single generation message.

        Args:
            message: The generation work item to enqueue.
        """
        ...

    def consume(self) -> AsyncIterator[GenerationMessage]:
        """Yield messages one at a time.

        The iterator blocks until a message is available.  Implementations
        must not yield the same message twice without an intervening call
        to ``ack()``.

        Yields:
            GenerationMessage instances in delivery order.
        """
        ...

    async def ack(self, message_id: str) -> None:
        """Acknowledge successful processing of a message.

        Args:
            message_id: The ``message_id`` from the delivered
                ``GenerationMessage``.
        """
        ...
