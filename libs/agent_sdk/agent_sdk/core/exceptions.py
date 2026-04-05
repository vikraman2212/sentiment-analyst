"""Domain exceptions for agent SDK consumers.

These are raised by SDK services; callers translate them into
protocol-appropriate error responses (HTTP, queue nack, etc.).
"""


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
    """Raised when the LLM fails to return valid structured JSON after retries."""

    def __init__(self, detail: str = "Extraction failed") -> None:
        self.detail = detail
        super().__init__(detail)


class LLMProviderError(Exception):
    """Raised when the LLM provider HTTP call fails (timeout, connection, 5xx)."""

    def __init__(self, detail: str = "LLM provider request failed") -> None:
        self.detail = detail
        super().__init__(detail)


class GenerationError(Exception):
    """Raised when the email generation pipeline fails."""

    def __init__(self, detail: str = "Generation failed") -> None:
        self.detail = detail
        super().__init__(detail)
