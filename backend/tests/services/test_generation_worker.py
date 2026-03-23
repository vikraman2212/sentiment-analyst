"""Unit tests for GenerationWorker._consume_loop().

Uses InMemorySpanExporter to assert span creation and W3C trace-context
propagation without a live Jaeger instance.  All external dependencies
(DB, GenerationService, GenerationFailureRepository) are mocked.
Tests follow AAA (Arrange → Act → Assert).
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

import app.services.generation_worker as worker_module
from app.core.message_queue import GenerationMessage
from app.services.generation_worker import GenerationWorker
from tests.services.conftest import get_metric_value, make_span_exporter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_ADVISOR_ID = uuid.uuid4()


def _make_message(trace_context: dict[str, str] | None = None) -> GenerationMessage:
    return GenerationMessage(
        client_id=_CLIENT_ID,
        advisor_id=_ADVISOR_ID,
        trigger_type="review_due",
        trace_context=trace_context or {},
    )


def _single_message_queue(message: GenerationMessage) -> MagicMock:
    """Return a queue mock whose consume() yields exactly one message then blocks."""

    async def _consume():  # type: ignore[return]
        yield message
        await asyncio.sleep(9_999)  # Block so the loop waits; test cancels the task

    queue = MagicMock()
    queue.consume.return_value = _consume()
    queue.ack = AsyncMock()
    return queue


def _patch_db(mock_session_cls: MagicMock) -> None:
    """Configure mock AsyncSessionLocal to work as an async context manager."""
    mock_db = AsyncMock()
    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_creates_span_with_correct_attributes() -> None:
    """GenerationWorker creates a generation.worker.process span with client attributes."""
    exporter, provider = make_span_exporter()
    tracer = provider.get_tracer(__name__)
    message = _make_message()
    queue = _single_message_queue(message)

    done = asyncio.Event()
    original_record = worker_module.record_worker_run

    def _signal_done(*args: object, **kwargs: object) -> None:
        original_record(*args, **kwargs)  # type: ignore[arg-type]
        done.set()

    with (
        patch("app.services.generation_worker.AsyncSessionLocal") as mock_session_cls,
        patch("app.services.generation_worker.GenerationService") as mock_gen_svc_cls,
        patch("app.services.generation_worker.GenerationFailureRepository"),
        patch.object(worker_module, "_tracer", tracer),
        patch.object(worker_module, "record_worker_run", side_effect=_signal_done),
    ):
        _patch_db(mock_session_cls)
        mock_gen_svc_cls.return_value.generate = AsyncMock()

        worker = GenerationWorker(queue=queue)
        worker._running = True  # Prevent immediate break on the first loop check
        task = asyncio.create_task(worker._consume_loop())
        await asyncio.wait_for(done.wait(), timeout=2.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "generation.worker.process"
    assert span.attributes["client_id"] == str(_CLIENT_ID)
    assert span.attributes["trigger_type"] == "review_due"


@pytest.mark.asyncio
async def test_worker_span_is_child_of_remote_context() -> None:
    """Worker span is linked to the remote context extracted from message.trace_context."""
    exporter, provider = make_span_exporter()
    tracer = provider.get_tracer(__name__)

    # Create a parent span and capture its W3C context into a carrier dict.
    carrier: dict[str, str] = {}
    with tracer.start_as_current_span("test.parent") as parent_span:
        TraceContextTextMapPropagator().inject(carrier)
        parent_trace_id = parent_span.get_span_context().trace_id

    message = _make_message(trace_context=carrier)
    queue = _single_message_queue(message)

    done = asyncio.Event()
    original_record = worker_module.record_worker_run

    def _signal_done(*args: object, **kwargs: object) -> None:
        original_record(*args, **kwargs)  # type: ignore[arg-type]
        done.set()

    with (
        patch("app.services.generation_worker.AsyncSessionLocal") as mock_session_cls,
        patch("app.services.generation_worker.GenerationService") as mock_gen_svc_cls,
        patch("app.services.generation_worker.GenerationFailureRepository"),
        patch.object(worker_module, "_tracer", tracer),
        patch.object(worker_module, "record_worker_run", side_effect=_signal_done),
    ):
        _patch_db(mock_session_cls)
        mock_gen_svc_cls.return_value.generate = AsyncMock()

        worker = GenerationWorker(queue=queue)
        worker._running = True  # Prevent immediate break on the first loop check
        task = asyncio.create_task(worker._consume_loop())
        await asyncio.wait_for(done.wait(), timeout=2.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    spans = exporter.get_finished_spans()
    worker_spans = [s for s in spans if s.name == "generation.worker.process"]
    assert len(worker_spans) == 1
    worker_span = worker_spans[0]
    assert worker_span.context.trace_id == parent_trace_id
    assert worker_span.parent is not None


@pytest.mark.asyncio
async def test_worker_records_success_metric() -> None:
    """record_worker_run('success', …) is invoked when generation completes without error."""
    _, provider = make_span_exporter()
    tracer = provider.get_tracer(__name__)
    before = get_metric_value(
        "sentiment_worker_messages_processed_total", {"status": "success"}
    )
    message = _make_message()
    queue = _single_message_queue(message)

    done = asyncio.Event()
    original_record = worker_module.record_worker_run

    def _signal_done(*args: object, **kwargs: object) -> None:
        original_record(*args, **kwargs)  # type: ignore[arg-type]
        done.set()

    with (
        patch("app.services.generation_worker.AsyncSessionLocal") as mock_session_cls,
        patch("app.services.generation_worker.GenerationService") as mock_gen_svc_cls,
        patch("app.services.generation_worker.GenerationFailureRepository"),
        patch.object(worker_module, "_tracer", tracer),
        patch.object(worker_module, "record_worker_run", side_effect=_signal_done),
    ):
        _patch_db(mock_session_cls)
        mock_gen_svc_cls.return_value.generate = AsyncMock()

        worker = GenerationWorker(queue=queue)
        worker._running = True  # Prevent immediate break on the first loop check
        task = asyncio.create_task(worker._consume_loop())
        await asyncio.wait_for(done.wait(), timeout=2.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert (
        get_metric_value("sentiment_worker_messages_processed_total", {"status": "success"})
        == before + 1
    )


@pytest.mark.asyncio
async def test_worker_records_error_metric_on_generation_failure() -> None:
    """record_worker_run('error', …) is invoked when GenerationService raises."""
    _, provider = make_span_exporter()
    tracer = provider.get_tracer(__name__)
    before = get_metric_value(
        "sentiment_worker_messages_processed_total", {"status": "error"}
    )
    message = _make_message()
    queue = _single_message_queue(message)

    done = asyncio.Event()
    original_record = worker_module.record_worker_run

    def _signal_done(*args: object, **kwargs: object) -> None:
        original_record(*args, **kwargs)  # type: ignore[arg-type]
        done.set()

    with (
        patch("app.services.generation_worker.AsyncSessionLocal") as mock_session_cls,
        patch("app.services.generation_worker.GenerationService") as mock_gen_svc_cls,
        patch(
            "app.services.generation_worker.GenerationFailureRepository"
        ) as mock_failure_repo_cls,
        patch.object(worker_module, "_tracer", tracer),
        patch.object(worker_module, "record_worker_run", side_effect=_signal_done),
    ):
        _patch_db(mock_session_cls)
        mock_gen_svc_cls.return_value.generate = AsyncMock(
            side_effect=ValueError("generation exploded")
        )
        failure_mock = MagicMock()
        failure_mock.id = uuid.uuid4()
        mock_failure_repo_cls.return_value.create = AsyncMock(return_value=failure_mock)

        worker = GenerationWorker(queue=queue)
        worker._running = True  # Prevent immediate break on the first loop check
        task = asyncio.create_task(worker._consume_loop())
        await asyncio.wait_for(done.wait(), timeout=2.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert (
        get_metric_value("sentiment_worker_messages_processed_total", {"status": "error"})
        == before + 1
    )
