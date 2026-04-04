"""Contract tests for agent_sdk core protocols.

Verifies that:
- ``OllamaProvider`` satisfies the ``LLMProvider`` Protocol at runtime.
- ``InMemoryQueue`` satisfies the ``MessageQueue`` Protocol at runtime.
- ``RedisStreamQueue`` satisfies the ``MessageQueue`` Protocol at runtime.
- ``NoOpAuditLogger`` satisfies the ``AbstractAuditLogger`` Protocol at runtime.
- ``BaseAgent`` subclasses enforce the ``run()`` abstract method.
- ``AgentTrigger`` / ``AgentResult`` dataclasses are sane.
- ``GenerationMessage`` carries ``schema_version``.
"""

from __future__ import annotations

import uuid

import pytest

from agent_sdk.audit.logger import AbstractAuditLogger
from agent_sdk.audit.models import LLMAuditEvent, make_audit_event
from agent_sdk.audit.noop import NoOpAuditLogger
from agent_sdk.core.contracts import AgentResult, AgentTrigger, BaseAgent
from agent_sdk.core.llm_provider import LLMProvider
from agent_sdk.core.message_queue import GenerationMessage, MessageQueue
from agent_sdk.providers.llm.ollama import OllamaProvider
from agent_sdk.providers.queue.inmemory import InMemoryQueue

# ---------------------------------------------------------------------------
# Protocol structural checks
# ---------------------------------------------------------------------------


def test_ollama_provider_satisfies_llm_provider_protocol() -> None:
    provider = OllamaProvider()
    assert isinstance(provider, LLMProvider)


def test_inmemory_queue_satisfies_message_queue_protocol() -> None:
    queue = InMemoryQueue()
    assert isinstance(queue, MessageQueue)


def test_noop_audit_logger_satisfies_abstract_audit_logger_protocol() -> None:
    audit = NoOpAuditLogger()
    assert isinstance(audit, AbstractAuditLogger)


# ---------------------------------------------------------------------------
# RedisStreamQueue protocol check (class-level only — no live Redis needed)
# ---------------------------------------------------------------------------


def test_redis_stream_queue_satisfies_message_queue_protocol() -> None:
    from agent_sdk.providers.queue.redis import RedisStreamQueue

    queue = RedisStreamQueue(redis_url="redis://localhost:6379")
    assert isinstance(queue, MessageQueue)


# ---------------------------------------------------------------------------
# GenerationMessage schema version
# ---------------------------------------------------------------------------


def test_generation_message_has_schema_version() -> None:
    msg = GenerationMessage(
        client_id=uuid.uuid4(),
        advisor_id=uuid.uuid4(),
        trigger_type="review_due",
    )
    assert msg.schema_version == "1.0"


def test_generation_message_schema_version_is_overridable() -> None:
    msg = GenerationMessage(
        client_id=uuid.uuid4(),
        advisor_id=uuid.uuid4(),
        trigger_type="review_due",
        schema_version="2.0",
    )
    assert msg.schema_version == "2.0"


# ---------------------------------------------------------------------------
# AgentTrigger / AgentResult
# ---------------------------------------------------------------------------


def test_agent_trigger_defaults() -> None:
    trigger = AgentTrigger(
        client_id=uuid.uuid4(),
        advisor_id=uuid.uuid4(),
        trigger_type="review_due",
    )
    assert trigger.schema_version == "1.0"
    assert trigger.payload == {}


def test_agent_result_defaults() -> None:
    result = AgentResult(
        success=True,
        trigger_type="review_due",
        client_id=uuid.uuid4(),
    )
    assert result.schema_version == "1.0"
    assert result.output == {}
    assert result.error is None


# ---------------------------------------------------------------------------
# BaseAgent — ABC enforcement
# ---------------------------------------------------------------------------


def test_base_agent_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        BaseAgent()  # type: ignore[abstract]


def test_base_agent_subclass_must_implement_run() -> None:
    class IncompleteAgent(BaseAgent):
        pass  # missing run()

    with pytest.raises(TypeError):
        IncompleteAgent()  # type: ignore[abstract]


def test_base_agent_concrete_subclass_is_instantiable() -> None:
    class ConcreteAgent(BaseAgent):
        async def run(self, trigger: AgentTrigger) -> AgentResult:
            return AgentResult(
                success=True,
                trigger_type=trigger.trigger_type,
                client_id=trigger.client_id,
            )

    agent = ConcreteAgent()
    assert agent is not None


# ---------------------------------------------------------------------------
# BaseAgent — async run() round-trip
# ---------------------------------------------------------------------------


async def test_concrete_agent_run_returns_result() -> None:
    _client_id = uuid.uuid4()
    _advisor_id = uuid.uuid4()

    class EchoAgent(BaseAgent):
        async def run(self, trigger: AgentTrigger) -> AgentResult:
            return AgentResult(
                success=True,
                trigger_type=trigger.trigger_type,
                client_id=trigger.client_id,
                output={"echo": trigger.trigger_type},
            )

    agent = EchoAgent()
    trigger = AgentTrigger(
        client_id=_client_id,
        advisor_id=_advisor_id,
        trigger_type="review_due",
    )
    result = await agent.run(trigger)

    assert result.success is True
    assert result.trigger_type == "review_due"
    assert result.client_id == _client_id
    assert result.output == {"echo": "review_due"}


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------


def test_make_audit_event_converts_uuid() -> None:
    client_id = uuid.uuid4()
    event = make_audit_event(
        pipeline="generation",
        client_id=client_id,
        model="llama3.2",
        prompt="test prompt",
        response="test response",
        status="success",
        latency_ms=100.0,
        prompt_tokens=10,
        completion_tokens=5,
    )
    assert event.client_id == str(client_id)
    assert event.pipeline == "generation"
    assert event.status == "success"


async def test_noop_audit_logger_log_does_not_raise() -> None:
    audit = NoOpAuditLogger()
    event = LLMAuditEvent(
        pipeline="extraction",
        client_id=str(uuid.uuid4()),
        model="llama3.2",
        prompt="prompt",
        response="response",
        status="success",
        latency_ms=50.0,
        prompt_tokens=None,
        completion_tokens=None,
    )
    await audit.log(event)  # must not raise


# ---------------------------------------------------------------------------
# InMemoryQueue — basic publish / consume round-trip
# ---------------------------------------------------------------------------


async def test_inmemory_queue_publish_consume_roundtrip() -> None:
    queue = InMemoryQueue()
    client_id = uuid.uuid4()
    advisor_id = uuid.uuid4()

    msg = GenerationMessage(
        client_id=client_id,
        advisor_id=advisor_id,
        trigger_type="on_demand",
    )
    await queue.publish(msg)
    assert msg.message_id != ""  # assigned on publish

    received: GenerationMessage | None = None
    async for item in queue.consume():
        received = item
        break  # consume exactly one

    assert received is not None
    assert received.client_id == client_id
    assert received.trigger_type == "on_demand"


async def test_inmemory_queue_ack_is_noop() -> None:
    queue = InMemoryQueue()
    await queue.ack("any-message-id")  # must not raise
