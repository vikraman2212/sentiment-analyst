"""Unit tests for app.core.middleware.RequestCorrelationMiddleware.

Uses a minimal ASGI test harness so no real FastAPI app or database is needed.
Tests follow AAA (Arrange → Act → Assert).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
import structlog
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.middleware import RequestCorrelationMiddleware, _REQUEST_ID_HEADER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app() -> Starlette:
    """Build a minimal Starlette app wrapped with the correlation middleware."""

    async def echo(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", echo)])
    app.add_middleware(RequestCorrelationMiddleware)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_response_echoes_provided_request_id() -> None:
    """When X-Request-ID is supplied, it is echoed in the response header."""
    client = TestClient(_make_app(), raise_server_exceptions=True)
    given_id = str(uuid.uuid4())

    response = client.get("/", headers={_REQUEST_ID_HEADER: given_id})

    assert response.status_code == 200
    assert response.headers[_REQUEST_ID_HEADER] == given_id


def test_response_generates_request_id_when_absent() -> None:
    """When X-Request-ID is absent, the middleware generates a UUID."""
    client = TestClient(_make_app(), raise_server_exceptions=True)

    response = client.get("/")

    assert response.status_code == 200
    generated = response.headers.get(_REQUEST_ID_HEADER)
    assert generated is not None
    # Must be a valid UUID
    uuid.UUID(generated)


def test_different_requests_receive_different_ids() -> None:
    """Two requests without a header each receive a distinct generated ID."""
    client = TestClient(_make_app(), raise_server_exceptions=True)

    resp1 = client.get("/")
    resp2 = client.get("/")

    id1 = resp1.headers[_REQUEST_ID_HEADER]
    id2 = resp2.headers[_REQUEST_ID_HEADER]
    assert id1 != id2


def test_structlog_context_bound_with_request_id() -> None:
    """The middleware binds request_id into structlog contextvars."""
    captured: dict[str, str] = {}

    async def capture_ctx(request: Request) -> PlainTextResponse:
        captured.update(structlog.contextvars.get_contextvars())
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", capture_ctx)])
    app.add_middleware(RequestCorrelationMiddleware)

    given_id = "test-req-abc"
    TestClient(app).get("/", headers={_REQUEST_ID_HEADER: given_id})

    assert captured.get("request_id") == given_id


def test_structlog_context_includes_trace_ids_when_span_active() -> None:
    """When an active OTel span exists, trace_id and span_id are bound."""
    captured: dict[str, str] = {}

    async def capture_ctx(request: Request) -> PlainTextResponse:
        captured.update(structlog.contextvars.get_contextvars())
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", capture_ctx)])
    app.add_middleware(RequestCorrelationMiddleware)

    mock_span_ctx = MagicMock()
    mock_span_ctx.is_valid = True
    mock_span_ctx.trace_id = 0xABCD1234ABCD1234ABCD1234ABCD1234
    mock_span_ctx.span_id = 0x1234ABCD1234ABCD

    mock_span = MagicMock()
    mock_span.get_span_context.return_value = mock_span_ctx

    with patch("app.core.middleware.trace") as mock_trace:
        mock_trace.get_current_span.return_value = mock_span
        TestClient(app).get("/")

    assert "trace_id" in captured
    assert "span_id" in captured
    assert captured["trace_id"] == format(0xABCD1234ABCD1234ABCD1234ABCD1234, "032x")
    assert captured["span_id"] == format(0x1234ABCD1234ABCD, "016x")


def test_structlog_context_no_trace_ids_when_span_invalid() -> None:
    """When no valid OTel span is active, trace_id and span_id are NOT bound."""
    captured: dict[str, str] = {}

    async def capture_ctx(request: Request) -> PlainTextResponse:
        captured.update(structlog.contextvars.get_contextvars())
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", capture_ctx)])
    app.add_middleware(RequestCorrelationMiddleware)

    mock_span_ctx = MagicMock()
    mock_span_ctx.is_valid = False

    mock_span = MagicMock()
    mock_span.get_span_context.return_value = mock_span_ctx

    with patch("app.core.middleware.trace") as mock_trace:
        mock_trace.get_current_span.return_value = mock_span
        TestClient(app).get("/")

    assert "trace_id" not in captured
    assert "span_id" not in captured
