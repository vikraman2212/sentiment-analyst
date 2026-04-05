"""Domain exceptions for the Advisor Sentiment backend.

These are raised by services and repositories; routers translate them into
HTTP responses via the global exception handlers registered in ``app/main.py``.

``LLMProviderError`` is re-exported from ``agent_sdk`` so that SDK providers
(e.g. OllamaProvider) and backend routers share the same exception class.
"""

from agent_sdk.core.exceptions import LLMProviderError  # noqa: F401


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, detail: str = "Resource not found") -> None:
        self.detail = detail
        super().__init__(detail)


class ConflictError(Exception):
    """Raised when an operation violates a uniqueness or state constraint."""

    def __init__(self, detail: str = "Resource conflict") -> None:
        self.detail = detail
        super().__init__(detail)


class ExtractionError(Exception):
    """Raised when Ollama fails to return valid structured JSON after retries."""

    def __init__(self, detail: str = "Extraction failed") -> None:
        self.detail = detail
        super().__init__(detail)


class GenerationError(Exception):
    """Raised when the email generation pipeline fails."""

    def __init__(self, detail: str = "Generation failed") -> None:
        self.detail = detail
        super().__init__(detail)
