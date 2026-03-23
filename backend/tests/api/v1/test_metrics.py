"""Tests for the Prometheus metrics endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.telemetry import register_metrics_endpoint


def _make_test_app() -> FastAPI:
    """Return a minimal FastAPI app with only the metrics endpoint registered."""
    app = FastAPI()
    register_metrics_endpoint(app)
    return app


async def test_metrics_endpoint_returns_prometheus_payload() -> None:
    """GET /metrics returns a Prometheus-formatted payload and status 200."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_test_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "sentiment_extraction_requests_total" in response.text
    assert "sentiment_generation_requests_total" in response.text
    assert "sentiment_scheduler_runs_total" in response.text