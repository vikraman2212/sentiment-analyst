"""Shared pytest fixtures for the api/v1 test package.

Provides a reusable ``async_client`` factory helper so tests can spin up a
minimal FastAPI app with the router under test and a mocked ``get_db``
dependency — no database or infrastructure required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies.db import get_db


def make_app_with_router(router, *, include_exception_handlers: bool = True) -> FastAPI:
    """Build a minimal FastAPI app with only the given router registered.

    Exception handlers from ``app.main`` can optionally be included so that
    domain exceptions (NotFoundError, ConflictError, …) translate to the
    expected HTTP status codes.
    """
    app = FastAPI()

    if include_exception_handlers:
        from fastapi.responses import JSONResponse

        from app.core.exceptions import (
            ConflictError,
            ExtractionError,
            GenerationError,
            LLMProviderError,
            NotFoundError,
        )

        @app.exception_handler(NotFoundError)
        async def _not_found(request, exc):
            return JSONResponse(status_code=404, content={"detail": exc.detail})

        @app.exception_handler(ConflictError)
        async def _conflict(request, exc):
            return JSONResponse(status_code=409, content={"detail": exc.detail})

        @app.exception_handler(GenerationError)
        async def _generation_error(request, exc):
            return JSONResponse(status_code=500, content={"detail": exc.detail})

        @app.exception_handler(LLMProviderError)
        async def _llm_error(request, exc):
            return JSONResponse(status_code=503, content={"detail": exc.detail})

        @app.exception_handler(ExtractionError)
        async def _extraction_error(request, exc):
            return JSONResponse(status_code=422, content={"detail": exc.detail})

    app.include_router(router)

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    return app


def async_client(app: FastAPI) -> AsyncClient:
    """Return an ``AsyncClient`` wired to the given ASGI app."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
