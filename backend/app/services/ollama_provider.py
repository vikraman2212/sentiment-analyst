"""Ollama LLM provider — concrete implementation of LLMProvider.

Sends completion requests to a local Ollama instance via its
``/api/generate`` REST endpoint and maps the response to the shared
``LLMResult`` type.
"""

import time

import httpx
import structlog

from app.core.llm_provider import LLMResult

logger = structlog.get_logger(__name__)


class OllamaProvider:
    """LLMProvider implementation backed by a local Ollama server.

    Args:
        base_url: Ollama HTTP base URL (e.g. ``http://localhost:11434``).
        timeout_seconds: Per-request timeout passed to ``httpx.AsyncClient``.
    """

    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self._base_url = base_url
        self._timeout = float(timeout_seconds)

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        format: str | None = None,
        model: str,
    ) -> LLMResult:
        """Send a prompt to Ollama and return the completion.

        Args:
            prompt: The user/main prompt text.
            system: Optional system-level instruction.
            format: ``"json"`` for JSON-enforced output, ``None`` for free-form.
            model: Ollama model name (e.g. ``"llama3.2"``).

        Returns:
            LLMResult populated from the Ollama response body.

        Raises:
            LLMProviderError: On any HTTP or connection failure.
        """
        from app.core.exceptions import LLMProviderError

        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system is not None:
            payload["system"] = system
        if format is not None:
            payload["format"] = format

        log = logger.bind(model=model)
        log.info("ollama_request_started")

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            ) as client:
                response = await client.post("/api/generate", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            latency_ms = (time.monotonic() - start) * 1_000
            log.error(
                "ollama_http_error",
                error=str(exc),
                latency_ms=round(latency_ms, 1),
                exc_info=True,
            )
            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        latency_ms = (time.monotonic() - start) * 1_000
        body = response.json()
        raw = body.get("response", "")
        prompt_tokens: int | None = body.get("prompt_eval_count")
        completion_tokens: int | None = body.get("eval_count")

        log.info(
            "ollama_response_received",
            chars=len(raw),
            latency_ms=round(latency_ms, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return LLMResult(
            response=raw,
            prompt=prompt,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )
