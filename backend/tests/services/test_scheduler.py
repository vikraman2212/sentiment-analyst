"""Unit tests for SchedulerService.

All external dependencies (AdvisorRepository, ContextAssemblyService,
MessageQueue) are mocked so no network or database is required.
Tests follow AAA (Arrange → Act → Assert).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.message_queue import GenerationMessage
from app.schemas.context_assembly import AssembledContext, FinancialSummary
from app.services.scheduler import SchedulerService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ADVISOR_ID = uuid.uuid4()
_CLIENT_A = uuid.uuid4()
_CLIENT_B = uuid.uuid4()


def _make_advisor(advisor_id: uuid.UUID = _ADVISOR_ID) -> MagicMock:
    advisor = MagicMock()
    advisor.id = advisor_id
    return advisor


def _make_context(client_id: uuid.UUID) -> AssembledContext:
    return AssembledContext(
        client_id=client_id,
        client_name="Test Client",
        financial_summary=FinancialSummary(
            total_aum=Decimal("500_000"),
            ytd_return_pct=Decimal("3.1"),
            risk_profile="moderate",
        ),
        context_tags=[],
        prompt_block="## Client Profile\nName: Test Client",
    )


def _make_queue() -> AsyncMock:
    """Return an async mock satisfying the MessageQueue protocol."""
    queue = AsyncMock()
    queue.publish = AsyncMock()
    return queue


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_happy_path_two_clients() -> None:
    """publish_pending_generations publishes one message per eligible client."""
    # Arrange
    queue = _make_queue()
    svc = SchedulerService(queue=queue)

    with (
        patch("app.services.scheduler.AsyncSessionLocal") as mock_session_cls,
        patch("app.services.scheduler.AdvisorRepository") as mock_advisor_repo_cls,
        patch("app.services.scheduler.ContextAssemblyService") as mock_context_svc_cls,
    ):
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        advisor_repo = AsyncMock()
        advisor_repo.list_all = AsyncMock(return_value=[_make_advisor()])
        mock_advisor_repo_cls.return_value = advisor_repo

        context_svc = AsyncMock()
        context_svc.list_needing_review = AsyncMock(
            return_value=[_make_context(_CLIENT_A), _make_context(_CLIENT_B)]
        )
        mock_context_svc_cls.return_value = context_svc

        # Act
        published = await svc.publish_pending_generations()

    # Assert
    assert published == 2
    assert queue.publish.call_count == 2

    calls = queue.publish.call_args_list
    published_ids = {call.args[0].client_id for call in calls}
    assert published_ids == {_CLIENT_A, _CLIENT_B}

    for call in calls:
        msg: GenerationMessage = call.args[0]
        assert msg.trigger_type == "review_due"
        assert msg.advisor_id == _ADVISOR_ID


@pytest.mark.asyncio
async def test_publish_no_advisors_returns_zero() -> None:
    """publish_pending_generations returns 0 and publishes nothing when there are no advisors."""
    # Arrange
    queue = _make_queue()
    svc = SchedulerService(queue=queue)

    with (
        patch("app.services.scheduler.AsyncSessionLocal") as mock_session_cls,
        patch("app.services.scheduler.AdvisorRepository") as mock_advisor_repo_cls,
        patch("app.services.scheduler.ContextAssemblyService"),
    ):
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        advisor_repo = AsyncMock()
        advisor_repo.list_all = AsyncMock(return_value=[])
        mock_advisor_repo_cls.return_value = advisor_repo

        # Act
        published = await svc.publish_pending_generations()

    # Assert
    assert published == 0
    queue.publish.assert_not_called()


@pytest.mark.asyncio
async def test_publish_no_eligible_clients_returns_zero() -> None:
    """publish_pending_generations returns 0 when no clients need review."""
    # Arrange
    queue = _make_queue()
    svc = SchedulerService(queue=queue)

    with (
        patch("app.services.scheduler.AsyncSessionLocal") as mock_session_cls,
        patch("app.services.scheduler.AdvisorRepository") as mock_advisor_repo_cls,
        patch("app.services.scheduler.ContextAssemblyService") as mock_context_svc_cls,
    ):
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        advisor_repo = AsyncMock()
        advisor_repo.list_all = AsyncMock(return_value=[_make_advisor()])
        mock_advisor_repo_cls.return_value = advisor_repo

        context_svc = AsyncMock()
        context_svc.list_needing_review = AsyncMock(return_value=[])
        mock_context_svc_cls.return_value = context_svc

        # Act
        published = await svc.publish_pending_generations()

    # Assert
    assert published == 0
    queue.publish.assert_not_called()


@pytest.mark.asyncio
async def test_publish_advisor_failure_continues_to_next() -> None:
    """A failure for one advisor does not abort publishing for subsequent advisors."""
    # Arrange
    queue = _make_queue()
    svc = SchedulerService(queue=queue)

    advisor_ok_id = uuid.uuid4()
    advisor_fail_id = uuid.uuid4()

    with (
        patch("app.services.scheduler.AsyncSessionLocal") as mock_session_cls,
        patch("app.services.scheduler.AdvisorRepository") as mock_advisor_repo_cls,
        patch("app.services.scheduler.ContextAssemblyService") as mock_context_svc_cls,
    ):
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        advisor_repo = AsyncMock()
        advisor_repo.list_all = AsyncMock(
            return_value=[_make_advisor(advisor_fail_id), _make_advisor(advisor_ok_id)]
        )
        mock_advisor_repo_cls.return_value = advisor_repo

        # First advisor raises, second succeeds with one client
        context_svc = AsyncMock()
        context_svc.list_needing_review = AsyncMock(
            side_effect=[RuntimeError("DB timeout"), [_make_context(_CLIENT_A)]]
        )
        mock_context_svc_cls.return_value = context_svc

        # Act
        published = await svc.publish_pending_generations()

    # Assert — only the successful advisor's client was published
    assert published == 1
    assert queue.publish.call_count == 1
    msg: GenerationMessage = queue.publish.call_args.args[0]
    assert msg.client_id == _CLIENT_A
    assert msg.advisor_id == advisor_ok_id
