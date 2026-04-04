"""LLM provider factory — resolves the configured backend at runtime.

Reads ``settings.LLM_PROVIDER`` and returns the matching concrete
``LLMProvider`` implementation from ``agent_sdk``.
Usable as a FastAPI ``Depends()`` factory or called directly in service
constructors.
"""

from agent_sdk.core.llm_provider import LLMProvider
from agent_sdk.providers.llm.ollama import OllamaProvider

from app.core.config import settings


def get_llm_provider() -> LLMProvider:
    """Return the LLM provider configured via ``LLM_PROVIDER`` env var.

    Raises:
        ValueError: If the configured provider name is not recognised.
    """
    if settings.LLM_PROVIDER == "ollama":
        return OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            timeout_seconds=settings.OLLAMA_TIMEOUT_SECONDS,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
