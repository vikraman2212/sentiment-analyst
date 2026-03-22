"""Tests for the health endpoints: GET /api/v1/health and GET /api/v1/health/ready.

All external-dependency calls (database, storage, opensearch) are mocked so
that the test suite runs without any infrastructure. Tests follow AAA.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.middleware import _REQUEST_ID_HEADER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_app():
    """Return a minimal FastAPI app with only the health router registered."""
    from fastapi import FastAPI

    from app.api.v1.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)
    return app


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


async def test_liveness_returns_200() -> None:
    """GET /health returns 200 with status ok."""
    async with AsyncClient(transport=ASGITransport(app=_make_test_app()), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /health/ready — all dependencies healthy
# ---------------------------------------------------------------------------


async def test_readiness_returns_200_when_all_deps_ok() -> None:
    """GET /health/ready returns 200 when database, storage and opensearch are up."""
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock(execute=AsyncMock()))
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_storage = AsyncMock()
    mock_storage.ensure_bucket_exists = AsyncMock()

    mock_os_client = AsyncMock()
    mock_os_client.ping = AsyncMock(return_value=True)

    with (
        patch("app.api.v1.health.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.api.v1.health.storage_service", mock_storage),
        patch("app.api.v1.health.get_opensearch_client", return_value=mock_os_client),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=_make_test_app()), base_url="http://test"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["storage"] == "ok"
    assert body["checks"]["opensearch"] == "ok"


# ---------------------------------------------------------------------------
# GET /health/ready — individual dependency failures
# ---------------------------------------------------------------------------


async def test_readiness_returns_503_when_database_fails() -> None:
    """GET /health/ready returns 503 when the database is unreachable."""
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(side_effect=Exception("db down"))
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_storage = AsyncMock()
    mock_storage.ensure_bucket_exists = AsyncMock()

    mock_os_client = AsyncMock()
    mock_os_client.ping = AsyncMock(return_value=True)

    with (
        patch("app.api.v1.health.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.api.v1.health.storage_service", mock_storage),
        patch("app.api.v1.health.get_opensearch_client", return_value=mock_os_client),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=_make_test_app()), base_url="http://test"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "unavailable"
    assert body["checks"]["storage"] == "ok"
    assert body["checks"]["opensearch"] == "ok"


async def test_readiness_returns_503_when_storage_fails() -> None:
    """GET /health/ready returns 503 when MinIO/storage is unreachable."""
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock(execute=AsyncMock()))
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_storage = AsyncMock()
    mock_storage.ensure_bucket_exists = AsyncMock(side_effect=Exception("minio down"))

    mock_os_client = AsyncMock()
    mock_os_client.ping = AsyncMock(return_value=True)

    with (
        patch("app.api.v1.health.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.api.v1.health.storage_service", mock_storage),
        patch("app.api.v1.health.get_opensearch_client", return_value=mock_os_client),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=_make_test_app()), base_url="http://test"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["storage"] == "unavailable"
    assert body["checks"]["opensearch"] == "ok"


async def test_readiness_returns_503_when_opensearch_fails() -> None:
    """GET /health/ready returns 503 when OpenSearch is unreachable."""
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock(execute=AsyncMock()))
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_storage = AsyncMock()
    mock_storage.ensure_bucket_exists = AsyncMock()

    mock_os_client = AsyncMock()
    mock_os_client.ping = AsyncMock(side_effect=Exception("opensearch down"))

    with (
        patch("app.api.v1.health.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.api.v1.health.storage_service", mock_storage),
        patch("app.api.v1.health.get_opensearch_client", return_value=mock_os_client),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=_make_test_app()), base_url="http://test"
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["storage"] == "ok"
    assert body["checks"]["opensearch"] == "unavailable"
