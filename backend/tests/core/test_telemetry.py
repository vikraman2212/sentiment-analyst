"""Unit tests for app.core.telemetry.

Verifies that configure_telemetry() is a no-op when disabled and
bootstraps providers when enabled, that shutdown_telemetry() cleans up,
and that all metric recording helpers correctly increment counters and
observe histograms.
Tests use unittest.mock to avoid any real exporter connections.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from tests.services.conftest import get_metric_value

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_telemetry_module() -> None:
    """Reset module-level provider references between tests."""
    import app.core.telemetry as tel

    tel._tracer_provider = None
    tel._meter_provider = None


# ---------------------------------------------------------------------------
# configure_telemetry — disabled path
# ---------------------------------------------------------------------------


def test_configure_telemetry_disabled_returns_early(monkeypatch: pytest.MonkeyPatch) -> None:
    """When OTEL_ENABLED=False, configure_telemetry() is a no-op."""
    import app.core.telemetry as tel

    _reset_telemetry_module()
    monkeypatch.setattr(tel.settings, "OTEL_ENABLED", False)

    tel.configure_telemetry()

    assert tel._tracer_provider is None
    assert tel._meter_provider is None


# ---------------------------------------------------------------------------
# configure_telemetry — enabled path
# ---------------------------------------------------------------------------


def test_configure_telemetry_enabled_sets_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """When OTEL_ENABLED=True, providers are created and registered globally."""
    import app.core.telemetry as tel

    _reset_telemetry_module()
    monkeypatch.setattr(tel.settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(tel.settings, "OTEL_SERVICE_NAME", "test-service")
    monkeypatch.setattr(tel.settings, "OTEL_ENDPOINT", "http://localhost:4318")

    mock_tracer_provider = MagicMock(spec=TracerProvider)
    mock_meter_provider = MagicMock(spec=MeterProvider)

    with (
        patch.object(tel, "_build_tracer_provider", return_value=mock_tracer_provider),
        patch.object(tel, "_build_meter_provider", return_value=mock_meter_provider),
        patch.object(tel, "_instrument_libraries") as mock_instrument,
        patch.object(trace, "set_tracer_provider") as mock_set_tracer,
        patch.object(metrics, "set_meter_provider") as mock_set_meter,
    ):
        tel.configure_telemetry()

    assert tel._tracer_provider is mock_tracer_provider
    assert tel._meter_provider is mock_meter_provider
    mock_set_tracer.assert_called_once_with(mock_tracer_provider)
    mock_set_meter.assert_called_once_with(mock_meter_provider)
    mock_instrument.assert_called_once()

    _reset_telemetry_module()


# ---------------------------------------------------------------------------
# shutdown_telemetry
# ---------------------------------------------------------------------------


def test_shutdown_telemetry_calls_shutdown_on_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """shutdown_telemetry() calls shutdown() on both providers and clears refs."""
    import app.core.telemetry as tel

    mock_tracer_provider = MagicMock(spec=TracerProvider)
    mock_meter_provider = MagicMock(spec=MeterProvider)
    tel._tracer_provider = mock_tracer_provider
    tel._meter_provider = mock_meter_provider

    tel.shutdown_telemetry()

    mock_tracer_provider.shutdown.assert_called_once()
    mock_meter_provider.shutdown.assert_called_once()
    assert tel._tracer_provider is None
    assert tel._meter_provider is None


def test_shutdown_telemetry_noop_when_disabled() -> None:
    """shutdown_telemetry() is safe to call when providers are None (disabled)."""
    import app.core.telemetry as tel

    _reset_telemetry_module()

    # Should not raise
    tel.shutdown_telemetry()

    assert tel._tracer_provider is None
    assert tel._meter_provider is None


# ---------------------------------------------------------------------------
# Metric recording helpers
# ---------------------------------------------------------------------------


def test_record_extraction_run_success_increments_counters() -> None:
    """record_extraction_run increments request counter, duration histogram, and tags counter."""
    from app.core.telemetry import record_extraction_run

    before_count = get_metric_value("sentiment_extraction_requests_total", {"status": "success"})
    before_duration = get_metric_value(
        "sentiment_extraction_duration_seconds_count", {"status": "success"}
    )
    before_tags = get_metric_value("sentiment_extraction_tags_saved_total")

    record_extraction_run(status="success", duration_seconds=1.5, saved_count=3)

    assert (
        get_metric_value("sentiment_extraction_requests_total", {"status": "success"})
        == before_count + 1
    )
    assert (
        get_metric_value(
            "sentiment_extraction_duration_seconds_count", {"status": "success"}
        )
        == before_duration + 1
    )
    assert get_metric_value("sentiment_extraction_tags_saved_total") == before_tags + 3


def test_record_extraction_run_zero_saved_count_skips_tags() -> None:
    """record_extraction_run with saved_count=0 does not touch the tags counter."""
    from app.core.telemetry import record_extraction_run

    before_tags = get_metric_value("sentiment_extraction_tags_saved_total")

    record_extraction_run(status="error", duration_seconds=0.1)

    assert get_metric_value("sentiment_extraction_tags_saved_total") == before_tags


def test_record_generation_run_increments_counters() -> None:
    """record_generation_run increments the generation request counter and histogram."""
    from app.core.telemetry import record_generation_run

    before_count = get_metric_value("sentiment_generation_requests_total", {"status": "success"})
    before_duration = get_metric_value(
        "sentiment_generation_duration_seconds_count", {"status": "success"}
    )

    record_generation_run(status="success", duration_seconds=2.0)

    assert (
        get_metric_value("sentiment_generation_requests_total", {"status": "success"})
        == before_count + 1
    )
    assert (
        get_metric_value(
            "sentiment_generation_duration_seconds_count", {"status": "success"}
        )
        == before_duration + 1
    )


def test_record_scheduler_run_increments_counters_and_published() -> None:
    """record_scheduler_run increments scheduler counters and published message count."""
    from app.core.telemetry import record_scheduler_run

    before_runs = get_metric_value("sentiment_scheduler_runs_total", {"status": "success"})
    before_duration = get_metric_value(
        "sentiment_scheduler_duration_seconds_count", {"status": "success"}
    )
    before_published = get_metric_value("sentiment_scheduler_messages_published_total")

    record_scheduler_run(status="success", duration_seconds=0.5, published_count=5)

    assert (
        get_metric_value("sentiment_scheduler_runs_total", {"status": "success"})
        == before_runs + 1
    )
    assert (
        get_metric_value(
            "sentiment_scheduler_duration_seconds_count", {"status": "success"}
        )
        == before_duration + 1
    )
    assert (
        get_metric_value("sentiment_scheduler_messages_published_total")
        == before_published + 5
    )


def test_record_scheduler_run_zero_published_skips_messages_counter() -> None:
    """record_scheduler_run with published_count=0 does not touch the messages counter."""
    from app.core.telemetry import record_scheduler_run

    before_published = get_metric_value("sentiment_scheduler_messages_published_total")

    record_scheduler_run(status="success", duration_seconds=0.1, published_count=0)

    assert get_metric_value("sentiment_scheduler_messages_published_total") == before_published


def test_record_worker_run_increments_counters() -> None:
    """record_worker_run increments the worker message counter and duration histogram."""
    from app.core.telemetry import record_worker_run

    before_count = get_metric_value(
        "sentiment_worker_messages_processed_total", {"status": "success"}
    )
    before_duration = get_metric_value(
        "sentiment_worker_processing_duration_seconds_count", {"status": "success"}
    )

    record_worker_run(status="success", duration_seconds=0.8)

    assert (
        get_metric_value("sentiment_worker_messages_processed_total", {"status": "success"})
        == before_count + 1
    )
    assert (
        get_metric_value(
            "sentiment_worker_processing_duration_seconds_count", {"status": "success"}
        )
        == before_duration + 1
    )


def test_record_queue_publish_increments_counter_by_backend() -> None:
    """record_queue_publish increments the counter only for the specified backend label."""
    from app.core.telemetry import record_queue_publish

    before_inmemory = get_metric_value(
        "sentiment_queue_messages_published_total", {"backend": "inmemory"}
    )
    before_redis = get_metric_value(
        "sentiment_queue_messages_published_total", {"backend": "redis"}
    )

    record_queue_publish("inmemory")

    assert (
        get_metric_value("sentiment_queue_messages_published_total", {"backend": "inmemory"})
        == before_inmemory + 1
    )
    assert (
        get_metric_value("sentiment_queue_messages_published_total", {"backend": "redis"})
        == before_redis
    )


def test_set_inmemory_queue_depth_updates_gauge() -> None:
    """set_inmemory_queue_depth sets the gauge to the provided value."""
    from app.core.telemetry import set_inmemory_queue_depth

    set_inmemory_queue_depth(7)

    assert get_metric_value("sentiment_inmemory_queue_depth_messages") == 7.0


def test_record_llm_metrics_increments_all_counters() -> None:
    """record_llm_metrics increments call, duration, prompt-token, and completion-token metrics."""
    from app.core.telemetry import record_llm_metrics

    labels = {"pipeline": "generation", "model": "llama3.2", "status": "success"}
    token_labels = {"pipeline": "generation", "model": "llama3.2"}
    before_calls = get_metric_value("sentiment_llm_calls_total", labels)
    before_duration = get_metric_value("sentiment_llm_duration_seconds_count", labels)
    before_prompt = get_metric_value("sentiment_llm_prompt_tokens_total", token_labels)
    before_completion = get_metric_value("sentiment_llm_completion_tokens_total", token_labels)

    record_llm_metrics(
        pipeline="generation",
        model="llama3.2",
        status="success",
        duration_seconds=1.2,
        prompt_tokens=80,
        completion_tokens=40,
    )

    assert get_metric_value("sentiment_llm_calls_total", labels) == before_calls + 1
    assert get_metric_value("sentiment_llm_duration_seconds_count", labels) == before_duration + 1
    assert (
        get_metric_value("sentiment_llm_prompt_tokens_total", token_labels)
        == before_prompt + 80
    )
    assert (
        get_metric_value("sentiment_llm_completion_tokens_total", token_labels)
        == before_completion + 40
    )


def test_record_llm_metrics_none_tokens_do_not_increment_token_counters() -> None:
    """record_llm_metrics with None tokens skips the token counters."""
    from app.core.telemetry import record_llm_metrics

    token_labels = {"pipeline": "extraction", "model": "llama3.2"}
    before_prompt = get_metric_value("sentiment_llm_prompt_tokens_total", token_labels)
    before_completion = get_metric_value("sentiment_llm_completion_tokens_total", token_labels)

    record_llm_metrics(
        pipeline="extraction",
        model="llama3.2",
        status="error",
        duration_seconds=0.5,
        prompt_tokens=None,
        completion_tokens=None,
    )

    assert get_metric_value("sentiment_llm_prompt_tokens_total", token_labels) == before_prompt
    assert (
        get_metric_value("sentiment_llm_completion_tokens_total", token_labels)
        == before_completion
    )
