"""API contract tests for the audio router — webhook endpoint.

Covers: valid webhook, wrong secret, non-ObjectCreated events,
non-audio extensions, malformed object key, and empty Records.
The background task helper (_run_extraction) is mocked at the module level
so no real services are invoked.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.api.v1.conftest import async_client, make_app_with_router

_CLIENT_ID = uuid.uuid4()
_OBJECT_KEY = f"{_CLIENT_ID}/abc123.webm"
_SECRET = "test-webhook-secret"


def _make_app():
    from app.api.v1.audio import router

    return make_app_with_router(router)


def _webhook_payload(
    event_name: str = "s3:ObjectCreated:Put",
    object_key: str = _OBJECT_KEY,
) -> dict:
    return {
        "Records": [
            {
                "eventName": event_name,
                "s3": {
                    "bucket": {"name": "audio-uploads"},
                    "object": {"key": object_key, "size": 1024, "contentType": "audio/webm"},
                },
            }
        ]
    }


# ---------------------------------------------------------------------------
# POST /audio/webhook — happy path
# ---------------------------------------------------------------------------


async def test_webhook_accepted_and_background_task_queued() -> None:
    """Valid webhook returns 200 and queues the background extraction task."""
    app = _make_app()

    with (
        patch("app.core.config.settings.MINIO_WEBHOOK_SECRET", _SECRET),
        patch("app.api.v1.audio._run_extraction", new_callable=AsyncMock) as mock_extract,
    ):
        async with async_client(app) as client:
            response = await client.post(
                "/audio/webhook",
                json=_webhook_payload(),
                headers={"Authorization": _SECRET},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    # httpx ASGITransport runs BackgroundTasks synchronously, so the mock
    # will have been awaited exactly once with the correct arguments.
    mock_extract.assert_awaited_once_with(_CLIENT_ID, _OBJECT_KEY)


# ---------------------------------------------------------------------------
# POST /audio/webhook — auth failures
# ---------------------------------------------------------------------------


async def test_webhook_missing_auth_returns_403() -> None:
    """No Authorization header returns 403."""
    app = _make_app()

    with patch("app.core.config.settings.MINIO_WEBHOOK_SECRET", _SECRET):
        async with async_client(app) as client:
            response = await client.post("/audio/webhook", json=_webhook_payload())

    assert response.status_code == 403


async def test_webhook_wrong_secret_returns_403() -> None:
    """Wrong Authorization value returns 403."""
    app = _make_app()

    with patch("app.core.config.settings.MINIO_WEBHOOK_SECRET", _SECRET):
        async with async_client(app) as client:
            response = await client.post(
                "/audio/webhook",
                json=_webhook_payload(),
                headers={"Authorization": "wrong-secret"},
            )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /audio/webhook — filtering
# ---------------------------------------------------------------------------


async def test_webhook_ignores_delete_events() -> None:
    """s3:ObjectRemoved events are silently ignored."""
    app = _make_app()

    with (
        patch("app.core.config.settings.MINIO_WEBHOOK_SECRET", _SECRET),
        patch("app.api.v1.audio._run_extraction", new_callable=AsyncMock) as mock_extract,
    ):
        async with async_client(app) as client:
            response = await client.post(
                "/audio/webhook",
                json=_webhook_payload(event_name="s3:ObjectRemoved:Delete"),
                headers={"Authorization": _SECRET},
            )

    assert response.status_code == 200
    mock_extract.assert_not_called()


async def test_webhook_ignores_non_audio_extension() -> None:
    """Objects with non-audio extensions are skipped without queuing a task."""
    app = _make_app()
    key = f"{_CLIENT_ID}/document.pdf"

    with (
        patch("app.core.config.settings.MINIO_WEBHOOK_SECRET", _SECRET),
        patch("app.api.v1.audio._run_extraction", new_callable=AsyncMock) as mock_extract,
    ):
        async with async_client(app) as client:
            response = await client.post(
                "/audio/webhook",
                json=_webhook_payload(object_key=key),
                headers={"Authorization": _SECRET},
            )

    assert response.status_code == 200
    mock_extract.assert_not_called()


async def test_webhook_ignores_invalid_client_id_prefix() -> None:
    """Object key with a non-UUID prefix is skipped gracefully."""
    app = _make_app()

    with (
        patch("app.core.config.settings.MINIO_WEBHOOK_SECRET", _SECRET),
        patch("app.api.v1.audio._run_extraction", new_callable=AsyncMock) as mock_extract,
    ):
        async with async_client(app) as client:
            response = await client.post(
                "/audio/webhook",
                json=_webhook_payload(object_key="not-a-uuid/recording.webm"),
                headers={"Authorization": _SECRET},
            )

    assert response.status_code == 200
    mock_extract.assert_not_called()


async def test_webhook_empty_records_returns_accepted() -> None:
    """Payload with no Records still returns 200 accepted."""
    app = _make_app()

    with patch("app.core.config.settings.MINIO_WEBHOOK_SECRET", _SECRET):
        async with async_client(app) as client:
            response = await client.post(
                "/audio/webhook",
                json={"Records": []},
                headers={"Authorization": _SECRET},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
