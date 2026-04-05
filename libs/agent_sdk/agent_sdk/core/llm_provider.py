"""LLM provider abstraction — shared types and protocol.

Defines a provider-agnostic interface so that extraction and generation
pipelines are decoupled from any specific inference backend (Ollama,
OpenAI, Anthropic).  Concrete implementations live in
``agent_sdk.providers.llm``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResult:
    """Provider-agnostic output from a single LLM completion call.

    Attributes:
        response: Raw text response from the model.
        prompt: The prompt as submitted to the provider.
        prompt_tokens: Number of tokens in the prompt, if reported by the provider.
        completion_tokens: Number of tokens in the completion, if reported.
        latency_ms: Wall-clock latency of the provider call in milliseconds.
    """

    response: str
    prompt: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float


@runtime_checkable
class LLMProvider(Protocol):
    """Structural interface every LLM backend must satisfy.

    Callers pass the model name and optional parameters per-call so
    the same provider instance can serve both extraction and generation
    pipelines with different models.
    """

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        format: str | None = None,
        model: str,
    ) -> LLMResult:
        """Send a prompt and return the model's completion.

        Args:
            prompt: The user/main prompt text.
            system: Optional system prompt (not all backends support this separately).
            format: Response format hint — ``"json"`` for structured output,
                ``None`` for free-form text.
            model: Model identifier (e.g. ``"llama3.2"``, ``"gpt-4o"``).

        Returns:
            ``LLMResult`` with the model's response and telemetry metadata.
        """
        ...
