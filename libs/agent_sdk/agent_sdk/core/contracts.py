"""Base agent contract and shared execution dataclasses.

Every autonomous agent must subclass ``BaseAgent`` and implement ``run()``.
The ``AgentTrigger`` and ``AgentResult`` dataclasses are the only types
that cross the queue/agent boundary — keep them stable.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

_SCHEMA_VERSION = "1.0"


@dataclass
class AgentTrigger:
    """A unit of work delivered to an agent from the queue or a direct call.

    Attributes:
        client_id: Target client UUID.
        advisor_id: Advisor who owns the client.
        trigger_type: A label describing what initiated this work
            (e.g. ``"review_due"``, ``"on_demand"``).
        payload: Optional extra key/value context for the agent.
        schema_version: Envelope schema version — increment only on breaking changes.
    """

    client_id: uuid.UUID
    advisor_id: uuid.UUID
    trigger_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: str = _SCHEMA_VERSION


@dataclass
class AgentResult:
    """The outcome of a single agent execution.

    Attributes:
        success: ``True`` when the agent completed its pipeline without error.
        trigger_type: Echoed from the originating ``AgentTrigger``.
        client_id: Target client UUID echoed from the trigger.
        output: Agent-specific key/value output (e.g. draft IDs, tag counts).
        error: Human-readable error description when ``success`` is ``False``.
        schema_version: Envelope schema version.
    """

    success: bool
    trigger_type: str
    client_id: uuid.UUID
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    schema_version: str = _SCHEMA_VERSION


class BaseAgent(ABC):
    """Abstract base every autonomous agent must subclass.

    Agents receive an ``AgentTrigger`` from the queue (or a direct caller),
    execute their pipeline, and return an ``AgentResult``.

    Infrastructure concerns (DB session, LLM provider, queue, audit logger)
    are injected via the constructor.  Agents own their context assembly,
    prompts, and output persistence.

    Subclasses must implement ``run()``.
    """

    @abstractmethod
    async def run(self, trigger: AgentTrigger) -> AgentResult:
        """Execute the agent pipeline for the given trigger.

        Args:
            trigger: The work item delivered by the queue or caller.

        Returns:
            ``AgentResult`` describing success/failure and any output payload.
        """
        ...
