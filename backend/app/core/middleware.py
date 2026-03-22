"""Request correlation middleware.

Accepts or generates a ``X-Request-ID`` header for every incoming HTTP
request, binds it (plus OTel trace/span IDs when a span is active) to
structlog context variables so that all log lines emitted during the
request lifecycle carry the same correlation fields, and echoes the
request ID back on the response.
"""

from __future__ import annotations

import uuid

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Inject a request ID and optional OTel trace context into every request.

    For each request the middleware:

    1. Reads ``X-Request-ID`` from the incoming headers, or generates a new
       ``uuid4`` when the header is absent.
    2. Clears and re-seeds the structlog context-variable store so no state
       leaks between requests in the same worker.
    3. Binds ``request_id``, and — when an active OTel span is present —
       ``trace_id`` and ``span_id`` to the structlog context.
    4. Sets ``X-Request-ID`` on the outgoing response.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request, injecting correlation context."""
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Clear any stale context from a previous request on this coroutine.
        structlog.contextvars.clear_contextvars()

        ctx: dict[str, str] = {"request_id": request_id}

        span = trace.get_current_span()
        span_context = span.get_span_context()
        if span_context.is_valid:
            ctx["trace_id"] = format(span_context.trace_id, "032x")
            ctx["span_id"] = format(span_context.span_id, "016x")

        structlog.contextvars.bind_contextvars(**ctx)

        response: Response = await call_next(request)
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response
