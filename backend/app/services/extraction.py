"""LLM-backed JSON extraction service.

Sends a transcript to the configured LLM provider and extracts structured
context tags (category + content pairs).  The provider abstraction allows
swapping Ollama for OpenAI/Anthropic without changing this module.

Usage::

    from app.services.extraction import extraction_service
    count = await extraction_service.extract(transcript, client_id, interaction_id)
"""

import asyncio
import json
import uuid

import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ExtractionError
from app.core.llm_provider import LLMProvider
from app.core.prompts import EXTRACTION_PROMPT_TEMPLATE
from app.dependencies.llm import get_llm_provider
from app.repositories.client_context import ClientContextRepository
from app.schemas.client_context import ClientContextCreate, ContextCategory
from app.services.llm_audit import llm_audit_logger, make_audit_event


# Lenient parsing model — category is unconstrained str so that invalid
# categories from the LLM are soft-skipped rather than treated as a JSON error.
class _RawTag(BaseModel):
    category: str
    content: str


class _RawExtractionResult(BaseModel):
    tags: list[_RawTag]

logger = structlog.get_logger(__name__)

_VALID_CATEGORIES: set[str] = set(ContextCategory.__args__)  # type: ignore[attr-defined]


class ExtractionService:
    """Extract context tags from a transcript via the configured LLM provider.

    Retries once on JSON parse failure. Tags with unrecognised categories
    are soft-skipped (logged as warnings) so that a partially valid response
    still produces results.
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or get_llm_provider()

    async def extract(
        self,
        transcript: str,
        client_id: uuid.UUID,
        interaction_id: uuid.UUID,
        db: AsyncSession,
    ) -> int:
        """Send transcript to LLM provider, validate response, persist tags.

        Args:
            transcript: Full transcript text from faster-whisper.
            client_id: UUID of the client the interaction belongs to.
            interaction_id: UUID of the source interaction row.
            db: Active async database session.

        Returns:
            Number of context tags successfully persisted.

        Raises:
            ExtractionError: If the LLM returns invalid JSON on all attempts.
        """
        log = logger.bind(
            client_id=str(client_id),
            interaction_id=str(interaction_id),
        )
        log.info("extraction_started")

        prompt = EXTRACTION_PROMPT_TEMPLATE.format(transcript=transcript)
        model = settings.OLLAMA_EXTRACTION_MODEL

        result1 = await self._provider.complete(prompt, format="json", model=model)
        tags = self._parse_and_validate(result1.response, log, attempt=1)
        asyncio.create_task(
            llm_audit_logger.log(
                make_audit_event(
                    pipeline="extraction",
                    client_id=client_id,
                    model=model,
                    prompt=result1.prompt,
                    response=result1.response,
                    status="success" if tags is not None else "error",
                    latency_ms=result1.latency_ms,
                    prompt_tokens=result1.prompt_tokens,
                    completion_tokens=result1.completion_tokens,
                    error=None if tags is not None else "invalid_json_attempt_1",
                )
            )
        )

        if tags is None:
            log.warning("extraction_retry", reason="invalid_json_first_attempt")
            result2 = await self._provider.complete(prompt, format="json", model=model)
            tags = self._parse_and_validate(result2.response, log, attempt=2)
            asyncio.create_task(
                llm_audit_logger.log(
                    make_audit_event(
                        pipeline="extraction",
                        client_id=client_id,
                        model=model,
                        prompt=result2.prompt,
                        response=result2.response,
                        status="success" if tags is not None else "error",
                        latency_ms=result2.latency_ms,
                        prompt_tokens=result2.prompt_tokens,
                        completion_tokens=result2.completion_tokens,
                        error=None if tags is not None else "invalid_json_attempt_2",
                    )
                )
            )

        if tags is None:
            raise ExtractionError(
                "LLM returned invalid JSON after 2 attempts"
            )

        valid_payloads = self._filter_valid_tags(tags, client_id, interaction_id, log)
        if not valid_payloads:
            log.info("extraction_complete", saved=0)
            return 0

        saved = await ClientContextRepository(db).bulk_create(valid_payloads)
        log.info("extraction_complete", saved=len(saved))
        return len(saved)

    def _parse_and_validate(
        self,
        raw: str,
        log: structlog.BoundLogger,
        attempt: int,
    ) -> list[dict] | None:
        """Parse raw JSON string and validate against ExtractionResult schema.

        Returns list of tag dicts on success, None on any parse/validation error.
        """
        try:
            data = json.loads(raw)
            result = _RawExtractionResult.model_validate(data)
            return [t.model_dump() for t in result.tags]
        except (json.JSONDecodeError, ValidationError) as exc:
            log.warning(
                "extraction_parse_failed",
                attempt=attempt,
                error=str(exc),
                raw_snippet=raw[:200],
            )
            return None

    def _filter_valid_tags(
        self,
        tags: list[dict],
        client_id: uuid.UUID,
        interaction_id: uuid.UUID,
        log: structlog.BoundLogger,
    ) -> list[ClientContextCreate]:
        """Drop tags with unrecognised categories; build ClientContextCreate payloads."""
        valid: list[ClientContextCreate] = []
        for tag in tags:
            category = tag.get("category", "")
            if category not in _VALID_CATEGORIES:
                log.warning(
                    "extraction_tag_category_invalid",
                    category=category,
                    content_snippet=str(tag.get("content", ""))[:80],
                )
                continue
            valid.append(
                ClientContextCreate(
                    client_id=client_id,
                    category=category,
                    content=tag["content"],
                    source_interaction_id=interaction_id,
                )
            )
        return valid


extraction_service = ExtractionService()
