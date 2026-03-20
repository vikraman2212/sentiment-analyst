"""Pydantic schemas for Ollama JSON extraction output validation."""

from pydantic import BaseModel

from app.schemas.client_context import ContextCategory


class ExtractionTag(BaseModel):
    """A single extracted context tag from the Ollama LLM response."""

    category: ContextCategory
    content: str


class ExtractionResult(BaseModel):
    """The validated root object expected from Ollama's JSON output."""

    tags: list[ExtractionTag]
