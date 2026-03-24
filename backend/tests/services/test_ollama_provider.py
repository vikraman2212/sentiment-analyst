"""Unit tests for OllamaProvider.

httpx is mocked so no local Ollama server is required.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app.services.ollama_provider as _ollama_mod
from app.core.exceptions import LLMProviderError
from app.core.llm_provider import LLMResult
from app.services.ollama_provider import OllamaProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_URL = "http://localhost:11434"
_TIMEOUT = 60


def _make_httpx_response(body: dict) -> MagicMock:
    """Return a mock httpx.Response with the given JSON body."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = body
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_returns_llm_result() -> None:
    """Happy path: Ollama returns a valid response → LLMResult populated."""
    provider = OllamaProvider(_BASE_URL, _TIMEOUT)
    ollama_body = {
        "response": '{"tags": []}',
        "prompt_eval_count": 50,
        "eval_count": 20,
    }

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(ollama_body))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await provider.complete("Hello", format="json", model="llama3.2")

    assert isinstance(result, LLMResult)
    assert result.response == '{"tags": []}'
    assert result.prompt == "Hello"
    assert result.prompt_tokens == 50
    assert result.completion_tokens == 20
    assert result.latency_ms > 0


@pytest.mark.asyncio
async def test_complete_sends_system_prompt() -> None:
    """When system is provided, it appears in the Ollama payload."""
    provider = OllamaProvider(_BASE_URL, _TIMEOUT)
    ollama_body = {"response": "ok", "prompt_eval_count": 10, "eval_count": 5}

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(ollama_body))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await provider.complete(
            "Hello", system="You are helpful.", format=None, model="llama3.2"
        )

    call_kwargs = mock_http.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["system"] == "You are helpful."
    assert "format" not in payload


@pytest.mark.asyncio
async def test_complete_http_error_raises_llm_provider_error() -> None:
    """httpx.HTTPError → LLMProviderError."""
    provider = OllamaProvider(_BASE_URL, _TIMEOUT)

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(LLMProviderError, match="Ollama request failed"):
            await provider.complete("Hello", model="llama3.2")


@pytest.mark.asyncio
async def test_complete_missing_token_counts() -> None:
    """Ollama response without token counts → None values in LLMResult."""
    provider = OllamaProvider(_BASE_URL, _TIMEOUT)
    ollama_body = {"response": "answer"}

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(ollama_body))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await provider.complete("Hello", model="llama3.2")

    assert result.prompt_tokens is None
    assert result.completion_tokens is None


# ---------------------------------------------------------------------------
# Span / tracing tests
# ---------------------------------------------------------------------------


def _make_span_exporter() -> tuple[InMemorySpanExporter, TracerProvider]:
    """Return an in-memory span exporter wired to a fresh TracerProvider."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, provider


@pytest.fixture(autouse=False)
def span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Fixture: wire a fresh in-memory exporter into the ollama provider tracer."""
    exporter, provider = _make_span_exporter()
    original = _ollama_mod._tracer
    _ollama_mod._tracer = provider.get_tracer(__name__)
    yield exporter
    _ollama_mod._tracer = original


@pytest.mark.asyncio
async def test_complete_emits_llm_complete_span(span_exporter: InMemorySpanExporter) -> None:
    """Happy path: a single ``llm.complete`` span is recorded."""
    ollama_body = {"response": "ok", "prompt_eval_count": 10, "eval_count": 5}

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(ollama_body))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await OllamaProvider(_BASE_URL, _TIMEOUT).complete("Hello", model="llama3.2")

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "llm.complete"
    attrs = cast(dict[str, object], span.attributes or {})
    assert attrs["gen_ai.system"] == "ollama"
    assert attrs["gen_ai.request.model"] == "llama3.2"
    assert attrs["gen_ai.usage.prompt_tokens"] == 10
    assert attrs["gen_ai.usage.completion_tokens"] == 5
    assert attrs["gen_ai.usage.total_tokens"] == 15


@pytest.mark.asyncio
async def test_complete_span_events(span_exporter: InMemorySpanExporter) -> None:
    """Span contains request-started and response-received events."""
    ollama_body = {"response": "ok", "prompt_eval_count": 5, "eval_count": 3}

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(ollama_body))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await OllamaProvider(_BASE_URL, _TIMEOUT).complete("Hi", model="llama3.2")

    span = span_exporter.get_finished_spans()[0]
    event_names = [e.name for e in span.events]
    assert "llm.request.started" in event_names
    assert "llm.response.received" in event_names


@pytest.mark.asyncio
async def test_complete_span_error_status_on_http_failure(
    span_exporter: InMemorySpanExporter,
) -> None:
    """HTTP error → span status ERROR and exception recorded."""
    from opentelemetry.trace import StatusCode

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(LLMProviderError):
            await OllamaProvider(_BASE_URL, _TIMEOUT).complete("Hi", model="llama3.2")

    span = span_exporter.get_finished_spans()[0]
    assert span.status.status_code == StatusCode.ERROR
    assert any(e.name == "exception" for e in span.events)


@pytest.mark.asyncio
async def test_complete_prompt_capture_disabled_by_default(
    span_exporter: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gen_ai.prompt attribute must NOT be set when capture is disabled."""
    import app.core.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "OTEL_LLM_CAPTURE_PROMPTS", False)

    ollama_body = {"response": "ok", "prompt_eval_count": 5, "eval_count": 3}

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(ollama_body))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await OllamaProvider(_BASE_URL, _TIMEOUT).complete("Secret prompt", model="llama3.2")

    span = span_exporter.get_finished_spans()[0]
    attrs = cast(dict[str, object], span.attributes or {})
    assert "gen_ai.prompt" not in attrs


@pytest.mark.asyncio
async def test_complete_prompt_capture_enabled(
    span_exporter: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gen_ai.prompt attribute IS set when capture is explicitly enabled."""
    import app.core.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "OTEL_LLM_CAPTURE_PROMPTS", True)

    ollama_body = {"response": "ok", "prompt_eval_count": 5, "eval_count": 3}

    with patch("app.services.ollama_provider.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(ollama_body))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await OllamaProvider(_BASE_URL, _TIMEOUT).complete("My prompt", model="llama3.2")

    span = span_exporter.get_finished_spans()[0]
    attrs = cast(dict[str, object], span.attributes or {})
    assert attrs.get("gen_ai.prompt") == "My prompt"
