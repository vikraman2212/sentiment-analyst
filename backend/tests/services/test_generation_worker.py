"""Unit tests for GenerationWorker._handle() and dead-letter persistence.

The consumer-loop lifecycle (start/stop/consume) is tested at the SDK level.
These tests focus on the backend wiring:

- ``_handle()`` delegates to ``GenerationAgent.run()`` via the SDK worker.
- The ``on_failure`` callback persists failures to the dead-letter table.
- Metrics callbacks are invoked correctly.

Tests follow AAA (Arrange -> Act -> Assert).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agent_sdk.agents.generation.worker import GenerationWorker
from agent_sdk.core.contracts import AgentResult, AgentTrigger
from agent_sdk.core.message_queue import GenerationMessage

from app.services.generation_worker import persist_generation_failure

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_ADVISOR_ID = uuid.uuid4()


def _make_message() -> GenerationMessage:
    return GenerationMessage(
        client_id=_CLIENT_ID,
        advisor_id=_ADVISOR_ID,
        trigger_type="review_due",
    )


def _make_result(draft_id: uuid.UUID = uuid.uuid4()) -> AgentResult:
    return AgentResult(
        success=True,
        trigger_type="review_due",
        client_id=_CLIENT_ID,
        output={"draft_id": str(draft_id)},
    )


def _make_queue_with_one_message(message: GenerationMessage) -> MagicMock:
    """Return a queue mock whose consume() yields exactly one message then blocks."""

    async def _consume() -> AsyncGenerator[GenerationMessage, None]:  # type: ignore[return]
        yield message
        await asyncio.sleep(9_999)

    queue = MagicMock()
    queue.consume.return_value = _consume()
    queue.ack = AsyncMock()
    return queue


@asynccontextmanager
async def _mock_session_factory() -> AsyncGenerator[AsyncMock, None]:  # type: ignore[return]
    yield AsyncMock()


# ---------------------------------------------------------------------------
# _handle -- success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_calls_generation_agent_with_correct_args() -> None:
    """_handle() builds a GenerationAgent and calls run() with the right trigger."""
    message = _make_message()
    mock_session = AsyncMock()

    with patch(
        "agent_sdk.agents.generation.worker.GenerationAgent"
    ) as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=_make_result())

        worker = GenerationWorker(
            queue=MagicMock(),
            session_factory=_mock_session_factory,  # type: ignore[arg-type]
            context_reader_factory=MagicMock(return_value=AsyncMock()),
            draft_writer_factory=MagicMock(return_value=AsyncMock()),
            provider=AsyncMock(),
        )
        await worker._handle(message, mock_session)

    mock_agent_cls.assert_called_once()
    call = mock_agent_cls.return_value.run.call_args[0][0]
    assert isinstance(call, AgentTrigger)
    assert call.client_id == message.client_id
    assert call.trigger_type == message.trigger_type


@pytest.mark.asyncio
async def test_handle_records_success_metric() -> None:
    """_handle() triggers on_run_complete with status='success'."""
    message = _make_message()
    mock_on_run = MagicMock()

    with patch(
        "agent_sdk.agents.generation.worker.GenerationAgent"
    ) as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(return_value=_make_result())

        worker = GenerationWorker(
            queue=MagicMock(),
            session_factory=_mock_session_factory,  # type: ignore[arg-type]
            context_reader_factory=MagicMock(return_value=AsyncMock()),
            draft_writer_factory=MagicMock(return_value=AsyncMock()),
            provider=AsyncMock(),
            on_run_complete=mock_on_run,
        )
        await worker._handle(message, AsyncMock())

    mock_on_run.assert_called_once()
    assert mock_on_run.call_args[0][0] == "success"


# ---------------------------------------------------------------------------
# _handle -- failure path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_records_error_metric_and_reraises_on_failure() -> None:
    """_handle() invokes on_run_complete with status='error' and re-raises."""
    mock_on_run = MagicMock()
    message = _make_message()

    with patch(
        "agent_sdk.agents.generation.worker.GenerationAgent"
    ) as mock_agent_cls:
        mock_agent_cls.return_value.run = AsyncMock(
            side_effect=ValueError("generation exploded")
        )

        worker = GenerationWorker(
            queue=MagicMock(),
            session_factory=_mock_session_factory,  # type: ignore[arg-type]
            context_reader_factory=MagicMock(return_value=AsyncMock()),
            draft_writer_factory=MagicMock(return_value=AsyncMock()),
            provider=AsyncMock(),
            on_run_complete=mock_on_run,
        )
        with pytest.raises(ValueError, match="generation exploded"):
            await worker._handle(message, AsyncMock())

    mock_on_run.assert_called_once()
    assert mock_on_run.call_args[0][0] == "error"


# ---------------------------------------------------------------------------
# persist_generation_failure -- dead-letter callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_failure_writes_to_dead_letter_table() -> None:
    """persist_generation_failure() creates a GenerationFailure row."""
    message = _make_message()

    with patch("app.services.generation_worker.AsyncSessionLocal") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.generation_worker.GenerationFailureRepository"
        ) as mock_repo_cls:
            failure_mock = MagicMock()
            failure_mock.id = uuid.uuid4()
            mock_repo_cls.return_value.create = AsyncMock(return_value=failure_mock)

            await persist_generation_failure(message, RuntimeError("oops"))

    mock_repo_cls.assert_called_once_with(mock_db)
    create_call = mock_repo_cls.return_value.create.call_args
    assert create_call.kwargs["client_id"] == message.client_id
    assert create_call.kwargs["trigger_type"] == message.trigger_type
    assert "oops" in create_call.kwargs["error_detail"]


@pytest.mark.asyncio
async def test_persist_failure_does_not_raise_when_db_fails() -> None:
    """persist_generation_failure() swallows secondary DB errors."""
    message = _make_message()

    with patch("app.services.generation_worker.AsyncSessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("DB down")
        )
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Must not raise even though the DB session fails.
        await persist_generation_failure(message, RuntimeError("primary error"))


# ---------------------------------------------------------------------------
# Integration -- start / stop lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_start_stop_processes_message() -> None:
    """Full start/stop cycle: worker processes the enqueued message."""
    message = _make_message()
    queue = _make_queue_with_one_message(message)
    handled: list[GenerationMessage] = []

    with patch(
        "agent_sdk.agents.generation.worker.GenerationAgent"
    ) as mock_agent_cls:

        async def _fake_run(trigger: AgentTrigger) -> AgentResult:
            handled.append(message)
            return _make_result()

        mock_agent_cls.return_value.run = _fake_run

        worker = GenerationWorker(
            queue=queue,
            session_factory=_mock_session_factory,  # type: ignore[arg-type]
            context_reader_factory=MagicMock(return_value=AsyncMock()),
            draft_writer_factory=MagicMock(return_value=AsyncMock()),
            provider=AsyncMock(),
        )

        await worker.start()
        await asyncio.sleep(0.1)
        await worker.stop()

    assert len(handled) == 1
    assert handled[0].client_id == _CLIENT_ID
