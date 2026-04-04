"""Unit tests for SchedulerService.

Uses a mock ``IClientSource`` instead of patching internal repos, consistent
with the port/adaptor architecture.  Tests follow AAA (Arrange -> Act -> Assert).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from agent_sdk.agents.generation.scheduler import SchedulerService
from agent_sdk.core.message_queue import GenerationMessage

from app.services.scheduler import _on_publish_complete
from tests.services.conftest import get_metric_value

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ADVISOR_ID = uuid.uuid4()
_CLIENT_A = uuid.uuid4()
_CLIENT_B = uuid.uuid4()


def _make_queue() -> AsyncMock:
    queue = AsyncMock()
    queue.publish = AsyncMock()
    return queue


def _make_client_source(
    pairs: list[tuple[uuid.UUID, uuid.UUID]],
) -> AsyncMock:
    """Return a mock IClientSource returning the given (client_id, advisor_id) pairs."""
    source = AsyncMock()
    source.get_eligible_clients = AsyncMock(return_value=pairs)
    return source


@asynccontextmanager
async def _session_factory() -> AsyncGenerator[AsyncMock, None]:  # type: ignore[return]
    yield AsyncMock()


def _make_svc(
    client_source: AsyncMock,
    on_publish_complete: object = None,
) -> SchedulerService:
    return SchedulerService(
        queue=_make_queue(),
        session_factory=_session_factory,  # type: ignore[arg-type]
        client_source=client_source,
        on_publish_complete=on_publish_complete,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_happy_path_two_clients() -> None:
    """publish_pending_generations publishes one message per eligible client."""
    client_source = _make_client_source(
        [(_CLIENT_A, _ADVISOR_ID), (_CLIENT_B, _ADVISOR_ID)]
    )
    svc = SchedulerService(
        queue=(queue := _make_queue()),
        session_factory=_session_factory,  # type: ignore[arg-type]
        client_source=client_source,
        on_publish_complete=_on_publish_complete,
    )
    before_runs = get_metric_value(
        "sentiment_scheduler_runs_total", {"status": "success"}
    )
    before_duration = get_metric_value(
        "sentiment_scheduler_duration_seconds_count", {"status": "success"}
    )
    before_published = get_metric_value("sentiment_scheduler_messages_published_total")

    published = await svc.publish_pending_generations()

    assert published == 2
    assert queue.publish.call_count == 2
    calls = queue.publish.call_args_list
    published_ids = {call.args[0].client_id for call in calls}
    assert published_ids == {_CLIENT_A, _CLIENT_B}
    for call in calls:
        msg: GenerationMessage = call.args[0]
        assert msg.trigger_type == "review_due"
        assert msg.advisor_id == _ADVISOR_ID
    assert (
        get_metric_value("sentiment_scheduler_runs_total", {"status": "success"})
        == before_runs + 1
    )
    assert (
        get_metric_value(
            "sentiment_scheduler_duration_seconds_count", {"status": "success"}
        )
        == before_duration + 1
    )
    assert (
        get_metric_value("sentiment_scheduler_messages_published_total")
        == before_published + 2
    )


@pytest.mark.asyncio
async def test_publish_no_eligible_clients_returns_zero() -> None:
    """publish_pending_generations returns 0 and publishes nothing when list is empty."""
    client_source = _make_client_source([])
    svc = SchedulerService(
        queue=(queue := _make_queue()),
        session_factory=_session_factory,  # type: ignore[arg-type]
        client_source=client_source,
    )

    published = await svc.publish_pending_generations()

    assert published == 0
    queue.publish.assert_not_called()


@pytest.mark.asyncio
async def test_publish_message_has_dict_trace_context_carrier() -> None:
    """Each published GenerationMessage carries a dict trace_context carrier."""
    client_source = _make_client_source([(_CLIENT_A, _ADVISOR_ID)])
    svc = SchedulerService(
        queue=(queue := _make_queue()),
        session_factory=_session_factory,  # type: ignore[arg-type]
        client_source=client_source,
    )

    await svc.publish_pending_generations()

    msg: GenerationMessage = queue.publish.call_args.args[0]
    assert isinstance(msg.trace_context, dict)


@pytest.mark.asyncio
async def test_publish_injects_active_span_into_message_trace_context() -> None:
    """When an active OTel span is present, its traceparent is injected into each message."""
    from tests.services.conftest import make_span_exporter

    _, provider = make_span_exporter()
    tracer = provider.get_tracer(__name__)

    client_source = _make_client_source([(_CLIENT_A, _ADVISOR_ID)])
    svc = SchedulerService(
        queue=(queue := _make_queue()),
        session_factory=_session_factory,  # type: ignore[arg-type]
        client_source=client_source,
    )

    with tracer.start_as_current_span("test.scheduler.parent"):
        await svc.publish_pending_generations()

    msg: GenerationMessage = queue.publish.call_args.args[0]
    assert "traceparent" in msg.trace_context


@pytest.mark.asyncio
async def test_publish_on_publish_complete_callback_invoked() -> None:
    """on_publish_complete callback is called with (status, count, duration)."""
    mock_cb = MagicMock()
    client_source = _make_client_source([(_CLIENT_A, _ADVISOR_ID)])
    svc = SchedulerService(
        queue=_make_queue(),
        session_factory=_session_factory,  # type: ignore[arg-type]
        client_source=client_source,
        on_publish_complete=mock_cb,
    )

    await svc.publish_pending_generations()

    mock_cb.assert_called_once()
    status, count, duration = mock_cb.call_args[0]
    assert status == "success"
    assert count == 1
    assert isinstance(duration, float)
