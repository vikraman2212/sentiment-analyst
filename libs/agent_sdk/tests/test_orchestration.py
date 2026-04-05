"""Tests for BaseQueueWorker and BaseSchedulerPublisher.

Covers:
- ABC enforcement (cannot instantiate without implementing abstract methods).
- Worker start/stop lifecycle.
- Worker processes messages and calls _handle().
- Worker continues the consumer loop after a per-message failure.
- Worker calls _on_failure() on exception (the default logs; override tested too).
- Scheduler publish_all() calls _get_messages() and publishes each message.
- Scheduler skips failed individual publishes without aborting the fan-out.
- Scheduler returns 0 when _get_messages() returns [].
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest

from agent_sdk.core.message_queue import GenerationMessage, MessageQueue
from agent_sdk.core.session import IAsyncSession
from agent_sdk.orchestration.scheduler import BaseSchedulerPublisher
from agent_sdk.orchestration.worker import BaseQueueWorker

# ---------------------------------------------------------------------------
# Helpers — minimal fakes and fixtures
# ---------------------------------------------------------------------------


def _make_message(trigger_type: str = "review_due") -> GenerationMessage:
    return GenerationMessage(
        client_id=uuid.uuid4(),
        advisor_id=uuid.uuid4(),
        trigger_type=trigger_type,
    )


class _FakeSession:
    """Minimal IAsyncSession stub — execute() returns an empty mock."""

    async def execute(self, statement: object, params: object = None, **kw: object) -> object:
        return MagicMock()


@asynccontextmanager
async def _fake_session_factory() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


class _SingleShotQueue:
    """MessageQueue that yields exactly one message then blocks forever."""

    def __init__(self, message: GenerationMessage) -> None:
        self._message = message
        self._acked: list[str] = []

    async def publish(self, message: GenerationMessage) -> None:
        raise NotImplementedError

    async def ack(self, message_id: str) -> None:
        self._acked.append(message_id)

    async def consume(self) -> AsyncIterator[GenerationMessage]:  # type: ignore[override]
        yield self._message
        # Block so the worker loop waits rather than re-iterating with no messages.
        await asyncio.sleep(9999)


class _MultiShotQueue:
    """MessageQueue that yields a fixed list of messages in order, then blocks."""

    def __init__(self, messages: list[GenerationMessage]) -> None:
        self._messages = list(messages)
        self._acked: list[str] = []

    async def publish(self, message: GenerationMessage) -> None:
        raise NotImplementedError

    async def ack(self, message_id: str) -> None:
        self._acked.append(message_id)

    async def consume(self) -> AsyncIterator[GenerationMessage]:  # type: ignore[override]
        for msg in self._messages:
            yield msg
        await asyncio.sleep(9999)


# ---------------------------------------------------------------------------
# BaseQueueWorker — ABC enforcement
# ---------------------------------------------------------------------------


def test_base_queue_worker_cannot_be_instantiated() -> None:
    queue = MagicMock(spec=MessageQueue)
    with pytest.raises(TypeError):
        BaseQueueWorker(queue=queue, session_factory=_fake_session_factory)  # type: ignore[abstract]


def test_base_queue_worker_subclass_must_implement_handle() -> None:
    class Incomplete(BaseQueueWorker):
        pass  # missing _handle

    with pytest.raises(TypeError):
        Incomplete(queue=MagicMock(spec=MessageQueue), session_factory=_fake_session_factory)  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# BaseQueueWorker — lifecycle
# ---------------------------------------------------------------------------


async def test_worker_start_stop_lifecycle() -> None:
    msg = _make_message()
    queue = _SingleShotQueue(msg)

    handled: list[GenerationMessage] = []

    class _Worker(BaseQueueWorker):
        async def _handle(self, message: GenerationMessage, session: IAsyncSession) -> None:
            handled.append(message)

    worker = _Worker(queue=queue, session_factory=_fake_session_factory)  # type: ignore[arg-type]
    assert not worker._running
    await worker.start()
    assert worker._running

    # Give the task a moment to consume the single message.
    await asyncio.sleep(0.05)
    await worker.stop()
    assert not worker._running
    assert len(handled) == 1
    assert handled[0].client_id == msg.client_id


async def test_worker_start_is_idempotent() -> None:
    queue = _SingleShotQueue(_make_message())

    class _Worker(BaseQueueWorker):
        async def _handle(self, message: GenerationMessage, session: IAsyncSession) -> None:
            pass

    worker = _Worker(queue=queue, session_factory=_fake_session_factory)  # type: ignore[arg-type]
    await worker.start()
    first_task = worker._task
    await worker.start()  # second call must be a no-op
    assert worker._task is first_task
    await worker.stop()


async def test_worker_stop_before_start_is_safe() -> None:
    queue = _SingleShotQueue(_make_message())

    class _Worker(BaseQueueWorker):
        async def _handle(self, message: GenerationMessage, session: IAsyncSession) -> None:
            pass

    worker = _Worker(queue=queue, session_factory=_fake_session_factory)  # type: ignore[arg-type]
    await worker.stop()  # must not raise


# ---------------------------------------------------------------------------
# BaseQueueWorker — error isolation and _on_failure hook
# ---------------------------------------------------------------------------


async def test_worker_continues_loop_after_message_failure() -> None:
    """A failure on message 1 must not stop processing of message 2."""
    msg1 = _make_message("fail_me")
    msg2 = _make_message("succeed")
    queue = _MultiShotQueue([msg1, msg2])

    handled: list[GenerationMessage] = []

    class _Worker(BaseQueueWorker):
        async def _handle(self, message: GenerationMessage, session: IAsyncSession) -> None:
            if message.trigger_type == "fail_me":
                raise ValueError("intentional failure")
            handled.append(message)

    worker = _Worker(queue=queue, session_factory=_fake_session_factory)  # type: ignore[arg-type]
    await worker.start()
    await asyncio.sleep(0.1)
    await worker.stop()

    assert len(handled) == 1
    assert handled[0].trigger_type == "succeed"


async def test_worker_calls_on_failure_hook() -> None:
    msg = _make_message("will_fail")
    queue = _SingleShotQueue(msg)

    failures: list[tuple[GenerationMessage, Exception]] = []

    class _Worker(BaseQueueWorker):
        async def _handle(self, message: GenerationMessage, session: IAsyncSession) -> None:
            raise RuntimeError("failure")

        async def _on_failure(self, message: GenerationMessage, error: Exception) -> None:
            failures.append((message, error))

    worker = _Worker(queue=queue, session_factory=_fake_session_factory)  # type: ignore[arg-type]
    await worker.start()
    await asyncio.sleep(0.05)
    await worker.stop()

    assert len(failures) == 1
    assert failures[0][0].trigger_type == "will_fail"
    assert isinstance(failures[0][1], RuntimeError)


# ---------------------------------------------------------------------------
# BaseSchedulerPublisher — ABC enforcement
# ---------------------------------------------------------------------------


def test_base_scheduler_publisher_cannot_be_instantiated() -> None:
    queue = MagicMock(spec=MessageQueue)
    with pytest.raises(TypeError):
        BaseSchedulerPublisher(queue=queue, session_factory=_fake_session_factory)  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# BaseSchedulerPublisher — publish_all
# ---------------------------------------------------------------------------


async def test_scheduler_publish_all_returns_count() -> None:
    advisor_id = uuid.uuid4()
    messages = [
        GenerationMessage(client_id=uuid.uuid4(), advisor_id=advisor_id, trigger_type="review_due"),
        GenerationMessage(client_id=uuid.uuid4(), advisor_id=advisor_id, trigger_type="review_due"),
    ]

    published: list[GenerationMessage] = []

    class _FakeQueue:
        async def publish(self, message: GenerationMessage) -> None:
            published.append(message)

        async def ack(self, message_id: str) -> None:
            pass

        def consume(self) -> AsyncIterator[GenerationMessage]:  # type: ignore[override]
            raise NotImplementedError

    class _Publisher(BaseSchedulerPublisher):
        async def _get_messages(self, session: IAsyncSession) -> list[GenerationMessage]:
            return messages

    publisher = _Publisher(queue=_FakeQueue(), session_factory=_fake_session_factory)  # type: ignore[arg-type]
    count = await publisher.publish_all()

    assert count == 2
    assert len(published) == 2


async def test_scheduler_publish_all_returns_zero_when_no_messages() -> None:
    class _FakeQueue:
        async def publish(self, message: GenerationMessage) -> None:
            pass

        async def ack(self, message_id: str) -> None:
            pass

        def consume(self) -> AsyncIterator[GenerationMessage]:  # type: ignore[override]
            raise NotImplementedError

    class _Publisher(BaseSchedulerPublisher):
        async def _get_messages(self, session: IAsyncSession) -> list[GenerationMessage]:
            return []

    publisher = _Publisher(queue=_FakeQueue(), session_factory=_fake_session_factory)  # type: ignore[arg-type]
    count = await publisher.publish_all()
    assert count == 0


async def test_scheduler_skips_failed_publish_and_continues() -> None:
    """A publish failure on one message must not abort the remaining fan-out."""
    advisor_id = uuid.uuid4()
    messages = [
        GenerationMessage(client_id=uuid.uuid4(), advisor_id=advisor_id, trigger_type="t1"),
        GenerationMessage(client_id=uuid.uuid4(), advisor_id=advisor_id, trigger_type="t2"),
        GenerationMessage(client_id=uuid.uuid4(), advisor_id=advisor_id, trigger_type="t3"),
    ]

    published: list[str] = []
    call_count = 0

    class _PartiallyFailingQueue:
        async def publish(self, message: GenerationMessage) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("transient queue error")
            published.append(message.trigger_type)

        async def ack(self, message_id: str) -> None:
            pass

        def consume(self) -> AsyncIterator[GenerationMessage]:  # type: ignore[override]
            raise NotImplementedError

    class _Publisher(BaseSchedulerPublisher):
        async def _get_messages(self, session: IAsyncSession) -> list[GenerationMessage]:
            return messages

    publisher = _Publisher(  # type: ignore[arg-type]
        queue=_PartiallyFailingQueue(),
        session_factory=_fake_session_factory,
    )
    count = await publisher.publish_all()

    # 2 out of 3 should succeed
    assert count == 2
    assert "t1" in published
    assert "t3" in published
    assert "t2" not in published
