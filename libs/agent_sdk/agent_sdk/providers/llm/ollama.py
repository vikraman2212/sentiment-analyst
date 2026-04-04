"""Ollama LLM provider — concrete implementation of LLMProvider.

Sends completion requests to a local Ollama instance via its
``/api/generate`` REST endpoint and maps the response to the shared
``LLMResult`` type.

All backend-framework imports (``app.*``) are absent — configuration
is injected via constructor arguments so this class can be used by
any agent process or in isolation.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import structlog
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from agent_sdk.core.exceptions import LLMProviderError
from agent_sdk.core.llm_provider import LLMResult

logger = structlog.get_logger(__name__)

_tracer = trace.get_tracer(__name__)

# OpenTelemetry GenAI semantic convention attribute names
_GENAI_SYSTEM = "gen_ai.system"
_GENAI_REQUEST_MODEL = "gen_ai.request.model"
_GENAI_USAGE_PROMPT_TOKENS = "gen_ai.usage.prompt_tokens"
_GENAI_USAGE_COMPLETION_TOKENS = "gen_ai.usage.completion_tokens"
_GENAI_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"
_GENAI_PROMPT = "gen_ai.prompt"


class OllamaProvider:
    """``LLMProvider`` implementation backed by a local Ollama server.

    Args:
        base_url: Ollama HTTP base URL (e.g. ``"http://localhost:11434"``).
        timeout_seconds: Per-request timeout for the underlying
            ``httpx.AsyncClient``.
        max_retries: Maximum number of retry attempts on transient errors
            (``TransportError``, ``TimeoutException``).  4xx / 5xx
            status errors are not retried.
        backoff_factor: Exponential backoff multiplier between retries.
            Wait durations: 1 s, ``backoff_factor`` s, ``backoff_factor²`` s, …
        capture_prompts: When ``True``, raw prompt text is attached to
            OpenTelemetry spans.  Disable in production to avoid accidental
            PII capture.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout_seconds: int = 120,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        capture_prompts: bool = False,
    ) -> None:
        self._base_url = base_url
        self._timeout = float(timeout_seconds)
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._capture_prompts = capture_prompts

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
            ``LLMResult`` populated from the Ollama response body.

        Raises:
            LLMProviderError: On any HTTP or connection failure after all
                retry attempts are exhausted.
        """
        payload: dict[str, object] = {
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

        with _tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute(_GENAI_SYSTEM, "ollama")
            span.set_attribute(_GENAI_REQUEST_MODEL, model)
            if self._capture_prompts:
                span.set_attribute(_GENAI_PROMPT, prompt)

            span.add_event("llm.request.started")

            last_exc: httpx.HTTPError | None = None
            start = time.monotonic()
            attempt = 0

            for attempt in range(self._max_retries + 1):
                try:
                    async with httpx.AsyncClient(
                        base_url=self._base_url,
                        timeout=self._timeout,
                    ) as client:
                        response = await client.post("/api/generate", json=payload)
                        response.raise_for_status()
                    break  # success — exit retry loop
                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    last_exc = exc
                    if attempt < self._max_retries:
                        wait = self._backoff_factor**attempt
                        log.warning(
                            "ollama_retry",
                            attempt=attempt + 1,
                            max_retries=self._max_retries,
                            wait_seconds=round(wait, 2),
                            error=str(exc),
                        )
                        await asyncio.sleep(wait)
                    continue
                except httpx.HTTPStatusError as exc:
                    # 4xx / 5xx — do not retry
                    last_exc = exc
                    break

            if last_exc is not None:
                latency_ms = (time.monotonic() - start) * 1_000
                log.error(
                    "ollama_http_error",
                    error=str(last_exc),
                    latency_ms=round(latency_ms, 1),
                    attempts=attempt + 1,
                    exc_info=True,
                )
                span.record_exception(last_exc)
                span.set_status(StatusCode.ERROR, str(last_exc))
                raise LLMProviderError(f"Ollama request failed: {last_exc}") from last_exc

            latency_ms = (time.monotonic() - start) * 1_000
            body = response.json()
            raw: str = body.get("response", "")
            prompt_tokens: int | None = body.get("prompt_eval_count")
            completion_tokens: int | None = body.get("eval_count")

            if prompt_tokens is not None:
                span.set_attribute(_GENAI_USAGE_PROMPT_TOKENS, prompt_tokens)
            if completion_tokens is not None:
                span.set_attribute(_GENAI_USAGE_COMPLETION_TOKENS, completion_tokens)
            if prompt_tokens is not None and completion_tokens is not None:
                span.set_attribute(
                    _GENAI_USAGE_TOTAL_TOKENS, prompt_tokens + completion_tokens
                )

            span.add_event("llm.response.received")
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
