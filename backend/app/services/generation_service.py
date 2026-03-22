"""Email generation service.

Orchestrates the full generation pipeline:
  1. Assemble client context via ContextAssemblyService.
  2. Call the configured LLM provider with the context prompt block and a
     strict system prompt that enforces tone, length, and content rules.
  3. Normalise the raw LLM response to a clean email body string.
  4. Persist the result as a MessageDraft row.
  5. Fire an asynchronous LLM audit log event.
"""

import asyncio
import re
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import GenerationError, LLMProviderError
from app.core.llm_provider import LLMProvider
from app.dependencies.llm import get_llm_provider
from app.models.message_draft import MessageDraft
from app.schemas.message_draft import MessageDraftCreate
from app.services.context_assembly import ContextAssemblyService
from app.services.llm_audit import llm_audit_logger, make_audit_event
from app.services.message_draft_service import MessageDraftService

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """\
You are an AI assistant helping a financial advisor write personalised client emails.

Write a warm, professional email body for the advisor to send to the client named in the profile below.

Rules:
- Maximum 4 sentences.
- Refer to portfolio size approximately, rounded to the nearest $100,000 \
(e.g., "approximately $1.2M") — never print unrounded dollar amounts.
- Use only facts present in the profile. Do not invent information.
- Address the client by first name in the opening sentence.
- Return ONLY the email body text. No subject line, no "Dear ...", \
no sign-off, no markdown formatting.\
"""

# Patterns used by _normalize to strip accidental LLM output artefacts
_SUBJECT_RE = re.compile(r"^Subject:.*\n?", re.IGNORECASE | re.MULTILINE)
_SALUTATION_RE = re.compile(r"^Dear\s+\S.*,?\s*\n?", re.IGNORECASE | re.MULTILINE)
_SIGN_OFF_RE = re.compile(
    r"(Warm regards|Best regards|Kind regards|Sincerely|Best|Thanks),?\s*\n.*$",
    re.IGNORECASE | re.DOTALL,
)


class GenerationService:
    """Orchestrate LLM-based draft email generation for a single client.

    Accepts an injected ``LLMProvider`` for testing; falls back to the
    factory from ``app/dependencies/llm.py`` when not provided.
    """

    def __init__(self, db: AsyncSession, provider: LLMProvider | None = None) -> None:
        self._provider = provider or get_llm_provider()
        self._context_svc = ContextAssemblyService(db)
        self._draft_svc = MessageDraftService(db)

    async def generate(
        self,
        client_id: uuid.UUID,
        trigger_type: str,
    ) -> MessageDraft:
        """Generate a draft email for the given client and persist it.

        Args:
            client_id: UUID of the target client.
            trigger_type: Free-form label for what triggered this draft
                (e.g. ``"review_due"``).

        Returns:
            The persisted ``MessageDraft`` ORM instance.

        Raises:
            NotFoundError: If the client does not exist.
            GenerationError: If the LLM provider call fails.
        """
        log = logger.bind(client_id=str(client_id), trigger_type=trigger_type)
        log.info("generation_started")

        context = await self._context_svc.assemble(client_id)

        model = settings.OLLAMA_GENERATION_MODEL
        try:
            result = await self._provider.complete(
                context.prompt_block,
                system=_SYSTEM_PROMPT,
                model=model,
            )
        except LLMProviderError as exc:
            log.error("generation_llm_failed", error=exc.detail, exc_info=True)
            asyncio.create_task(
                llm_audit_logger.log(
                    make_audit_event(
                        pipeline="generation",
                        client_id=client_id,
                        model=model,
                        prompt=context.prompt_block,
                        response="",
                        status="error",
                        latency_ms=0.0,
                        prompt_tokens=None,
                        completion_tokens=None,
                        error=exc.detail,
                    )
                )
            )
            raise GenerationError(f"LLM provider failed: {exc.detail}") from exc

        generated_content = _normalize(result.response)
        log.info(
            "generation_llm_complete",
            model=model,
            latency_ms=round(result.latency_ms, 1),
            chars=len(generated_content),
        )

        asyncio.create_task(
            llm_audit_logger.log(
                make_audit_event(
                    pipeline="generation",
                    client_id=client_id,
                    model=model,
                    prompt=result.prompt,
                    response=result.response,
                    status="success",
                    latency_ms=result.latency_ms,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    error=None,
                )
            )
        )

        draft = await self._draft_svc.create(
            MessageDraftCreate(
                client_id=client_id,
                trigger_type=trigger_type,
                generated_content=generated_content,
            )
        )
        log.info("generation_complete", draft_id=str(draft.id))
        return draft


def _normalize(raw: str) -> str:
    """Strip accidental artefacts from the LLM response.

    Removes subject lines, salutations, and sign-offs that the model may
    include despite system prompt instructions.  Returns the trimmed body.
    """
    text = _SUBJECT_RE.sub("", raw)
    text = _SALUTATION_RE.sub("", text)
    text = _SIGN_OFF_RE.sub("", text)
    return text.strip()
