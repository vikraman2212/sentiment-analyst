"""Unit tests for MessageDraftService.list_all_pending.

All external dependencies (MessageDraftRepository, ClientRepository) are
mocked so no network or database is required.
Tests follow AAA (Arrange → Act → Assert).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.message_draft import PendingDraftResponse
from app.services.message_draft_service import MessageDraftService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_DRAFT_ID = uuid.uuid4()
_TAG_ID = uuid.uuid4()


def _make_context_tag(
    tag_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    category: str = "personal_interest",
    content: str = "Enjoys hiking",
    source_interaction_id: uuid.UUID | None = None,
) -> MagicMock:
    tag = MagicMock()
    tag.id = tag_id or uuid.uuid4()
    tag.client_id = client_id or _CLIENT_ID
    tag.category = category
    tag.content = content
    tag.source_interaction_id = source_interaction_id
    return tag


def _make_client(
    client_id: uuid.UUID | None = None,
    first_name: str = "Jane",
    last_name: str = "Doe",
    context_tags: list | None = None,
) -> MagicMock:
    client = MagicMock()
    client.id = client_id or _CLIENT_ID
    client.first_name = first_name
    client.last_name = last_name
    client.context_tags = context_tags if context_tags is not None else []
    return client


def _make_draft(
    draft_id: uuid.UUID | None = None,
    trigger_type: str = "review_due",
    generated_content: str = "Hi Jane, your portfolio is performing well.",
    client: MagicMock | None = None,
) -> MagicMock:
    draft = MagicMock()
    draft.id = draft_id or _DRAFT_ID
    draft.trigger_type = trigger_type
    draft.generated_content = generated_content
    draft.client = client or _make_client()
    return draft


def _make_service(pending_drafts: list | None = None) -> MessageDraftService:
    """Build a MessageDraftService with all dependencies mocked."""
    mock_repo = AsyncMock()
    mock_repo.list_all_pending = AsyncMock(return_value=pending_drafts or [])

    mock_client_repo = AsyncMock()

    svc = MessageDraftService.__new__(MessageDraftService)
    svc._repo = mock_repo
    svc._client_repo = mock_client_repo
    return svc


# ---------------------------------------------------------------------------
# list_all_pending tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_pending_empty_returns_empty_list() -> None:
    """list_all_pending returns an empty list when no pending drafts exist."""
    svc = _make_service(pending_drafts=[])

    result = await svc.list_all_pending()

    assert result == []


@pytest.mark.asyncio
async def test_list_all_pending_returns_pending_draft_response_list() -> None:
    """list_all_pending returns PendingDraftResponse instances."""
    draft = _make_draft()
    svc = _make_service(pending_drafts=[draft])

    result = await svc.list_all_pending()

    assert len(result) == 1
    assert isinstance(result[0], PendingDraftResponse)


@pytest.mark.asyncio
async def test_list_all_pending_maps_fields_correctly() -> None:
    """PendingDraftResponse fields are mapped from ORM relationships."""
    tag = _make_context_tag(tag_id=_TAG_ID, content="Enjoys cycling")
    client = _make_client(
        client_id=_CLIENT_ID,
        first_name="Alice",
        last_name="Smith",
        context_tags=[tag],
    )
    draft = _make_draft(
        draft_id=_DRAFT_ID,
        trigger_type="review_due",
        generated_content="Hi Alice, great news about your portfolio.",
        client=client,
    )
    svc = _make_service(pending_drafts=[draft])

    result = await svc.list_all_pending()

    assert len(result) == 1
    item = result[0]
    assert item.draft_id == _DRAFT_ID
    assert item.client_name == "Alice Smith"
    assert item.trigger_type == "review_due"
    assert item.generated_content == "Hi Alice, great news about your portfolio."
    assert len(item.context_used) == 1
    assert item.context_used[0].content == "Enjoys cycling"


@pytest.mark.asyncio
async def test_list_all_pending_no_context_tags_returns_empty_context_used() -> None:
    """When a client has no context tags, context_used is an empty list."""
    client = _make_client(context_tags=[])
    draft = _make_draft(client=client)
    svc = _make_service(pending_drafts=[draft])

    result = await svc.list_all_pending()

    assert result[0].context_used == []


@pytest.mark.asyncio
async def test_list_all_pending_multiple_drafts() -> None:
    """Multiple pending drafts are all returned."""
    draft_a = _make_draft(
        draft_id=uuid.uuid4(),
        client=_make_client(first_name="Bob", last_name="Jones"),
    )
    draft_b = _make_draft(
        draft_id=uuid.uuid4(),
        client=_make_client(first_name="Carol", last_name="White"),
    )
    svc = _make_service(pending_drafts=[draft_a, draft_b])

    result = await svc.list_all_pending()

    assert len(result) == 2
    names = {item.client_name for item in result}
    assert names == {"Bob Jones", "Carol White"}


@pytest.mark.asyncio
async def test_list_all_pending_context_used_fields_populated() -> None:
    """context_used items carry id, client_id, category, content, and source_interaction_id."""
    tag = _make_context_tag(
        tag_id=_TAG_ID,
        client_id=_CLIENT_ID,
        category="financial_goal",
        content="Save for retirement",
        source_interaction_id=None,
    )
    client = _make_client(client_id=_CLIENT_ID, context_tags=[tag])
    draft = _make_draft(client=client)
    svc = _make_service(pending_drafts=[draft])

    result = await svc.list_all_pending()

    ctx = result[0].context_used[0]
    assert ctx.id == _TAG_ID
    assert ctx.client_id == _CLIENT_ID
    assert ctx.category == "financial_goal"
    assert ctx.content == "Save for retirement"
    assert ctx.source_interaction_id is None
