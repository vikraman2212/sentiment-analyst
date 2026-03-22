"""API contract tests for the generation router.

Covers: POST /generate (success, NotFoundError, GenerationError)
and GET /generation/failures (success, empty).

All service/repository calls are mocked; no database or Ollama needed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.api.v1.conftest import async_client, make_app_with_router

_CLIENT_ID = uuid.uuid4()
_DRAFT_ID = uuid.uuid4()
_FAILURE_ID = uuid.uuid4()


def _mock_draft() -> MagicMock:
    m = MagicMock()
    m.id = _DRAFT_ID
    m.client_id = _CLIENT_ID
    m.trigger_type = "review_due"
    m.generated_content = "Hi John, your portfolio is performing well."
    return m


def _mock_failure() -> MagicMock:
    m = MagicMock()
    m.id = _FAILURE_ID
    m.client_id = _CLIENT_ID
    m.trigger_type = "review_due"
    m.message_id = "msg-001"
    m.error_detail = "Connection refused"
    m.failed_at = datetime(2026, 3, 23, 8, 0, 0, tzinfo=timezone.utc)
    m.resolved = False
    return m


def _make_app():
    from app.api.v1.generation import router
    return make_app_with_router(router)


# ---------------------------------------------------------------------------
# POST /generate
# ---------------------------------------------------------------------------


async def test_generate_draft_returns_201() -> None:
    """POST /generate returns 201 with draft payload on success."""
    app = _make_app()
    with patch("app.api.v1.generation.GenerationService") as mock_svc_cls:
        mock_svc_cls.return_value.generate = AsyncMock(return_value=_mock_draft())
        async with async_client(app) as client:
            response = await client.post(
                "/generate",
                json={"client_id": str(_CLIENT_ID), "trigger_type": "review_due"},
            )

    assert response.status_code == 201
    body = response.json()
    assert body["client_id"] == str(_CLIENT_ID)
    assert body["trigger_type"] == "review_due"
    assert "generated_content" in body


async def test_generate_draft_not_found_returns_404() -> None:
    """POST /generate returns 404 when the client does not exist."""
    from app.core.exceptions import NotFoundError

    app = _make_app()
    with patch("app.api.v1.generation.GenerationService") as mock_svc_cls:
        mock_svc_cls.return_value.generate = AsyncMock(
            side_effect=NotFoundError("Client not found")
        )
        async with async_client(app) as client:
            response = await client.post(
                "/generate",
                json={"client_id": str(uuid.uuid4()), "trigger_type": "review_due"},
            )

    assert response.status_code == 404


async def test_generate_draft_llm_error_returns_503() -> None:
    """POST /generate returns 503 when the LLM provider fails."""
    from app.core.exceptions import LLMProviderError

    app = _make_app()
    with patch("app.api.v1.generation.GenerationService") as mock_svc_cls:
        mock_svc_cls.return_value.generate = AsyncMock(
            side_effect=LLMProviderError("Ollama unreachable")
        )
        async with async_client(app) as client:
            response = await client.post(
                "/generate",
                json={"client_id": str(_CLIENT_ID), "trigger_type": "review_due"},
            )

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# GET /generation/failures
# ---------------------------------------------------------------------------


async def test_list_generation_failures_returns_200() -> None:
    """GET /generation/failures returns 200 with failure list."""
    app = _make_app()
    with patch(
        "app.api.v1.generation.GenerationFailureRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.list_unresolved = AsyncMock(
            return_value=[_mock_failure()]
        )
        async with async_client(app) as client:
            response = await client.get("/generation/failures")

    assert response.status_code == 200
    assert len(response.json()) == 1
    body = response.json()[0]
    assert body["resolved"] is False
    assert body["error_detail"] == "Connection refused"
    assert body["trigger_type"] == "review_due"


async def test_list_generation_failures_returns_empty_list() -> None:
    """GET /generation/failures returns 200 with [] when no failures exist."""
    app = _make_app()
    with patch(
        "app.api.v1.generation.GenerationFailureRepository"
    ) as mock_repo_cls:
        mock_repo_cls.return_value.list_unresolved = AsyncMock(return_value=[])
        async with async_client(app) as client:
            response = await client.get("/generation/failures")

    assert response.status_code == 200
    assert response.json() == []
