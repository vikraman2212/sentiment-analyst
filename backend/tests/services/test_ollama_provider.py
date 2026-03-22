"""Unit tests for OllamaProvider.

httpx is mocked so no local Ollama server is required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

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
