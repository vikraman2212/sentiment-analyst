"""API contract tests for the message_drafts router.

Covers: list pending, list by client, update status.
All service calls are mocked; no database required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from tests.api.v1.conftest import async_client, make_app_with_router

_CLIENT_ID = uuid.uuid4()
_DRAFT_ID = uuid.uuid4()


def _mock_draft() -> MagicMock:
    m = MagicMock()
    m.id = _DRAFT_ID
    m.client_id = _CLIENT_ID
    m.trigger_type = "review_due"
    m.generated_content = "Hi John, your portfolio looks great."
    m.status = "pending"
    return m


def _mock_pending_draft() -> MagicMock:
    m = MagicMock()
    m.draft_id = _DRAFT_ID
    m.client_name = "John Doe"
    m.trigger_type = "review_due"
    m.generated_content = "Hi John, your portfolio looks great."
    m.context_used = []
    return m


def _make_app():
    from app.api.v1.message_drafts import router
    return make_app_with_router(router)


# ---------------------------------------------------------------------------
# GET /drafts/pending
# ---------------------------------------------------------------------------


async def test_list_pending_drafts_returns_200() -> None:
    """GET /drafts/pending returns 200 with pending draft list."""
    app = _make_app()
    with patch("app.api.v1.message_drafts.MessageDraftService") as mock_svc_cls:
        mock_svc_cls.return_value.list_all_pending = AsyncMock(
            return_value=[_mock_pending_draft()]
        )
        async with async_client(app) as client:
            response = await client.get("/drafts/pending")

    assert response.status_code == 200
    assert len(response.json()) == 1
    body = response.json()[0]
    assert body["client_name"] == "John Doe"
    assert body["trigger_type"] == "review_due"


async def test_list_pending_drafts_returns_empty_list() -> None:
    """GET /drafts/pending returns 200 with empty list when no pending drafts."""
    app = _make_app()
    with patch("app.api.v1.message_drafts.MessageDraftService") as mock_svc_cls:
        mock_svc_cls.return_value.list_all_pending = AsyncMock(return_value=[])
        async with async_client(app) as client:
            response = await client.get("/drafts/pending")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /clients/{client_id}/message-drafts
# ---------------------------------------------------------------------------


async def test_list_client_message_drafts_returns_200() -> None:
    """GET /clients/{id}/message-drafts returns 200 with list."""
    app = _make_app()
    with patch("app.api.v1.message_drafts.MessageDraftService") as mock_svc_cls:
        mock_svc_cls.return_value.list_by_client = AsyncMock(
            return_value=[_mock_draft()]
        )
        async with async_client(app) as client:
            response = await client.get(f"/clients/{_CLIENT_ID}/message-drafts")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["trigger_type"] == "review_due"


async def test_list_client_message_drafts_not_found_returns_404() -> None:
    """GET /clients/{id}/message-drafts returns 404 for unknown client."""
    from app.core.exceptions import NotFoundError

    app = _make_app()
    with patch("app.api.v1.message_drafts.MessageDraftService") as mock_svc_cls:
        mock_svc_cls.return_value.list_by_client = AsyncMock(
            side_effect=NotFoundError("Client not found")
        )
        async with async_client(app) as client:
            response = await client.get(f"/clients/{uuid.uuid4()}/message-drafts")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /message-drafts/{draft_id}/status
# ---------------------------------------------------------------------------


async def test_update_draft_status_to_sent_returns_200() -> None:
    """PATCH /message-drafts/{id}/status returns 200 with updated status."""
    sent_draft = _mock_draft()
    sent_draft.status = "sent"

    app = _make_app()
    with patch("app.api.v1.message_drafts.MessageDraftService") as mock_svc_cls:
        mock_svc_cls.return_value.update_status = AsyncMock(return_value=sent_draft)
        async with async_client(app) as client:
            response = await client.patch(
                f"/message-drafts/{_DRAFT_ID}/status",
                json={"status": "sent"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "sent"


async def test_update_draft_status_not_found_returns_404() -> None:
    """PATCH /message-drafts/{id}/status returns 404 for unknown draft."""
    from app.core.exceptions import NotFoundError

    app = _make_app()
    with patch("app.api.v1.message_drafts.MessageDraftService") as mock_svc_cls:
        mock_svc_cls.return_value.update_status = AsyncMock(
            side_effect=NotFoundError("Draft not found")
        )
        async with async_client(app) as client:
            response = await client.patch(
                f"/message-drafts/{uuid.uuid4()}/status",
                json={"status": "sent"},
            )

    assert response.status_code == 404
