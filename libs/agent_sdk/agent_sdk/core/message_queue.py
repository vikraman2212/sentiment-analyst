"""Message queue abstraction — shared types and protocol.

Defines a provider-agnostic interface so that the scheduler publisher and
the generation worker are decoupled from any specific queue backend
(in-memory asyncio.Queue, Redis Streams, SQS, etc.).

Concrete implementations live in ``agent_sdk.providers.queue``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

_SCHEMA_VERSION = "1.0"


@dataclass
class GenerationMessage:
    """A single unit of work enqueued by the scheduler publisher.

    Attributes:
        client_id: Target client UUID.
        advisor_id: Advisor who owns the client.
        trigger_type: Label describing the origin of this work item
            (e.g. ``"review_due"``).
        message_id: Assigned by the queue implementation on ``publish``;
            passed back to ``ack``.
        trace_context: W3C TraceContext carrier for distributed trace propagation.
        schema_version: Envelope schema version for forward compatibility.
    """

    client_id: uuid.UUID
    advisor_id: uuid.UUID
    trigger_type: str
    message_id: str = ""
    trace_context: dict[str, str] = field(default_factory=dict)
    schema_version: str = _SCHEMA_VERSION


@runtime_checkable
class MessageQueue(Protocol):
    """Structural interface every queue backend must satisfy.

    The protocol mirrors ``LLMProvider`` — callers depend on this
    abstraction; concrete implementations are injected via the factory
    in ``agent_sdk.dependencies.factories``.
    """

    async def publish(self, message: GenerationMessage) -> None:
        """Enqueue a single generation message.

        Args:
            message: The generation work item to enqueue.
        """
        ...

    def consume(self) -> AsyncIterator[GenerationMessage]:
        """Yield messages one at a time, blocking when the queue is empty.

        Implementations must not yield the same message twice without an
        intervening call to ``ack()``.

        Yields:
            ``GenerationMessage`` instances in delivery order.
        """
        ...

    async def ack(self, message_id: str) -> None:
        """Acknowledge successful processing of a message.

        Args:
            message_id: The ``message_id`` from the delivered
                ``GenerationMessage``.
        """
        ...
