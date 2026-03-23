"""Shared test helpers for services tests."""

from __future__ import annotations

from prometheus_client import REGISTRY  # type: ignore[import-not-found]
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def make_span_exporter() -> tuple[InMemorySpanExporter, TracerProvider]:
    """Return an in-memory span exporter wired to a fresh TracerProvider."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, provider


def get_metric_value(name: str, labels: dict[str, str] | None = None) -> float:
    """Return the current Prometheus sample value or zero when absent."""
    sample = REGISTRY.get_sample_value(name, labels=labels)
    return float(sample or 0.0)
