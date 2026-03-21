"""Ollama JSON extraction service.

Sends a transcript to a local Ollama instance and extracts structured
context tags (category + content pairs) using ``format="json"`` enforcement.

Usage::

    from app.services.extraction import extraction_service
    count = await extraction_service.extract(transcript, client_id, interaction_id)
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass

import httpx
import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ExtractionError
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


@dataclass
class _OllamaResult:
    """Raw output captured from a single Ollama /api/generate call."""

    response: str
    prompt: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float

_EXTRACTION_PROMPT_TEMPLATE = """\
You are an AI assistant helping a financial advisor extract structured notes from a client meeting transcript.

Analyse the transcript below and extract context items. Return ONLY a JSON object in this exact format:
{{
  "tags": [
    {{"category": "<category>", "content": "<concise note>"}},
    ...
  ]
}}

Valid categories (use exactly as written):
- personal_interest
- financial_goal
- family_event
- risk_tolerance

Rules:
- Only include items clearly supported by the transcript.
- Each tag must have exactly the fields "category" and "content".
- Do not include any commentary, markdown, or text outside the JSON object.

Transcript:
{transcript}
"""


class ExtractionService:
    """Extract context tags from a transcript via Ollama's local API.

    Retries once on JSON parse failure. Tags with unrecognised categories
    are soft-skipped (logged as warnings) so that a partially valid response
    still produces results.
    """

    async def extract(
        self,
        transcript: str,
        client_id: uuid.UUID,
        interaction_id: uuid.UUID,
        db: AsyncSession,
    ) -> int:
        """Send transcript to Ollama, validate response, persist tags.

        Args:
            transcript: Full transcript text from faster-whisper.
            client_id: UUID of the client the interaction belongs to.
            interaction_id: UUID of the source interaction row.
            db: Active async database session.

        Returns:
            Number of context tags successfully persisted.

        Raises:
            ExtractionError: If Ollama returns invalid JSON on all attempts.
        """
        log = logger.bind(
            client_id=str(client_id),
            interaction_id=str(interaction_id),
        )
        log.info("extraction_started")

        result1 = await self._call_ollama(transcript, log)
        tags = self._parse_and_validate(result1.response, log, attempt=1)
        asyncio.create_task(
            llm_audit_logger.log(
                make_audit_event(
                    pipeline="extraction",
                    client_id=client_id,
                    model=settings.OLLAMA_MODEL,
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
            result2 = await self._call_ollama(transcript, log)
            tags = self._parse_and_validate(result2.response, log, attempt=2)
            asyncio.create_task(
                llm_audit_logger.log(
                    make_audit_event(
                        pipeline="extraction",
                        client_id=client_id,
                        model=settings.OLLAMA_MODEL,
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
                "Ollama returned invalid JSON after 2 attempts"
            )

        valid_payloads = self._filter_valid_tags(tags, client_id, interaction_id, log)
        if not valid_payloads:
            log.info("extraction_complete", saved=0)
            return 0

        saved = await ClientContextRepository(db).bulk_create(valid_payloads)
        log.info("extraction_complete", saved=len(saved))
        return len(saved)

    async def _call_ollama(
        self,
        transcript: str,
        log: structlog.BoundLogger,
    ) -> _OllamaResult:
        """POST to Ollama /api/generate and return an _OllamaResult.

        Captures end-to-end latency and token counts from the response body.
        """
        prompt = _EXTRACTION_PROMPT_TEMPLATE.format(transcript=transcript)
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        log.info("ollama_request_started", model=settings.OLLAMA_MODEL)
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                base_url=settings.OLLAMA_BASE_URL,
                timeout=60.0,
            ) as client:
                response = await client.post("/api/generate", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            log.error("ollama_http_error", error=str(exc), exc_info=True)
            raise ExtractionError(f"Ollama request failed: {exc}") from exc
        finally:
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
        return _OllamaResult(
            response=raw,
            prompt=prompt,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )

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
