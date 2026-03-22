"""Unit tests for app.core.telemetry.

Verifies that configure_telemetry() is a no-op when disabled and
bootstraps providers when enabled, and that shutdown_telemetry() cleans up.
Tests use unittest.mock to avoid any real exporter connections.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider


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
