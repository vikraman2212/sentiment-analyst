"""OpenTelemetry bootstrap: tracing and metrics provider initialisation.

Call ``configure_telemetry()`` once at application startup.  When
``settings.OTEL_ENABLED`` is ``False`` the global SDK providers remain as
built-in no-ops, so instrumented libraries emit nothing and no exporters are
initialised — safe for tests and local troubleshooting.

Call ``shutdown_telemetry()`` during application teardown to flush pending
spans/metrics and release exporter resources.
"""

from __future__ import annotations

import structlog
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Module-level references kept for shutdown; None when telemetry is disabled.
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None


def configure_telemetry() -> None:
    """Bootstrap OTel tracing and metrics providers.

    When ``settings.OTEL_ENABLED`` is ``False``, returns immediately so the
    SDK default no-op providers remain active.  No exporters or background
    threads are started.
    """
    global _tracer_provider, _meter_provider

    if not settings.OTEL_ENABLED:
        logger.info("telemetry_disabled")
        return

    resource = Resource.create(
        {ResourceAttributes.SERVICE_NAME: settings.OTEL_SERVICE_NAME}
    )

    _tracer_provider = _build_tracer_provider(resource)
    trace.set_tracer_provider(_tracer_provider)

    _meter_provider = _build_meter_provider(resource)
    metrics.set_meter_provider(_meter_provider)

    _instrument_libraries()

    logger.info(
        "telemetry_configured",
        service=settings.OTEL_SERVICE_NAME,
        endpoint=settings.OTEL_ENDPOINT,
    )


def shutdown_telemetry() -> None:
    """Flush and shut down OTel providers on application teardown.

    Safe to call even when telemetry is disabled; both providers will be
    ``None`` in that case and the function returns without error.
    """
    global _tracer_provider, _meter_provider

    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        logger.info("telemetry_tracer_provider_shutdown")
        _tracer_provider = None

    if _meter_provider is not None:
        _meter_provider.shutdown()
        logger.info("telemetry_meter_provider_shutdown")
        _meter_provider = None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_tracer_provider(resource: Resource) -> TracerProvider:
    """Build a TracerProvider with a BatchSpanProcessor backed by OTLP HTTP.

    Args:
        resource: OTel Resource describing this service instance.

    Returns:
        A configured TracerProvider ready to be set as the global provider.
    """
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    exporter = OTLPSpanExporter(endpoint=f"{settings.OTEL_ENDPOINT}/v1/traces")
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def _build_meter_provider(resource: Resource) -> MeterProvider:
    """Build a MeterProvider with a PeriodicExportingMetricReader backed by OTLP HTTP.

    Args:
        resource: OTel Resource describing this service instance.

    Returns:
        A configured MeterProvider ready to be set as the global provider.
    """
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

    exporter = OTLPMetricExporter(endpoint=f"{settings.OTEL_ENDPOINT}/v1/metrics")
    reader = PeriodicExportingMetricReader(exporter)
    return MeterProvider(resource=resource, metric_readers=[reader])


def _instrument_libraries() -> None:
    """Apply automatic instrumentation for FastAPI, httpx, and SQLAlchemy.

    Each instrumentor guards against double-instrumentation internally, so
    calling this function more than once (e.g., in tests) is safe and will
    not register duplicate spans or metrics.
    """
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    FastAPIInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()

    logger.info(
        "telemetry_instrumentation_applied",
        libraries=["fastapi", "httpx", "sqlalchemy"],
    )
