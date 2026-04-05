"""API contract tests for the generation router.

Covers: GET /generation/failures (success, empty).

All repository calls are mocked; no database or Ollama needed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from tests.api.v1.conftest import async_client, make_app_with_router

_CLIENT_ID = uuid.uuid4()
_FAILURE_ID = uuid.uuid4()


def _mock_failure() -> MagicMock:
    m = MagicMock()
    m.id = _FAILURE_ID
    m.client_id = _CLIENT_ID
    m.trigger_type = "review_due"
    m.message_id = "msg-001"
    m.error_detail = "Connection refused"
    m.failed_at = datetime(2026, 3, 23, 8, 0, 0, tzinfo=UTC)
    m.resolved = False
    return m


def _make_app():
    from app.api.v1.generation import router
    return make_app_with_router(router)


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
