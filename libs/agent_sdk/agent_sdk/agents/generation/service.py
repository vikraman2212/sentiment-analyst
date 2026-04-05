"""Generation agent — email draft generation pipeline.

Implements ``BaseAgent`` from the SDK contract.  The agent:

1. Checks for an existing pending draft (returns cached if present).
2. Assembles the client's context prompt block via the injected
   ``IContextAssembler``.
3. Calls the configured LLM provider.
4. Normalises the raw LLM response.
5. Persists the result via the injected ``IDraftWriter``.
6. Fires an async audit log event.

All external dependencies (DB access, LLM, audit) are injected so the
agent can be unit-tested without a database or running Ollama.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Callable
from time import perf_counter
from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from agent_sdk.agents.generation.ports import IContextAssembler, IDraftWriter
from agent_sdk.agents.generation.prompts import GENERATION_SYSTEM_PROMPT
from agent_sdk.audit.models import LLMAuditEvent, make_audit_event
from agent_sdk.core.contracts import AgentResult, AgentTrigger, BaseAgent
from agent_sdk.core.exceptions import GenerationError, LLMProviderError
from agent_sdk.core.llm_provider import LLMProvider

if TYPE_CHECKING:
    from agent_sdk.audit.logger import AbstractAuditLogger

logger = structlog.get_logger(__name__)
_tracer = trace.get_tracer(__name__)

# Patterns used by _normalize to strip accidental LLM output artefacts.
_SUBJECT_RE = re.compile(r"^Subject:.*\n?", re.IGNORECASE | re.MULTILINE)
_SALUTATION_RE = re.compile(r"^Dear\s+\S.*,?\s*\n?", re.IGNORECASE | re.MULTILINE)
_SIGN_OFF_RE = re.compile(
    r"(Warm regards|Best regards|Kind regards|Sincerely|Best|Thanks),?\s*\n.*$",
    re.IGNORECASE | re.DOTALL,
)


class GenerationAgent(BaseAgent):
    """Email-draft generation agent for a single client context.

    Accepts injected collaborators for context assembly, draft persistence,
    the LLM provider, and audit logging — making the core pipeline logic
    independently testable.

    Args:
        context_reader: Assembles the prompt block from client data.
        draft_writer: Persists and manages generated drafts.
        provider: LLM provider to call.  Required at runtime; tests supply
            a mock.
        audit_logger: Optional audit logger.  When ``None`` audit events
            are silently dropped.
        generation_model: LLM model identifier passed to the provider.
        system_prompt: Override the built-in system prompt.  When ``None``
            the default ``GENERATION_SYSTEM_PROMPT`` is used.
        on_llm_complete: Optional callback invoked after each LLM call with
            ``(model, status, duration_seconds, prompt_tokens, completion_tokens)``.
            Use this to record Prometheus metrics without coupling the agent
            to a specific metrics library.
    """

    def __init__(
        self,
        context_reader: IContextAssembler,
        draft_writer: IDraftWriter,
        provider: LLMProvider,
        audit_logger: AbstractAuditLogger | None = None,
        generation_model: str = "llama3.2",
        system_prompt: str | None = None,
        on_llm_complete: (
            Callable[[str, str, float, int | None, int | None], None] | None
        ) = None,
    ) -> None:
        self._context_reader = context_reader
        self._draft_writer = draft_writer
        self._provider = provider
        self._audit_logger = audit_logger
        self._model = generation_model
        self._system_prompt = system_prompt or GENERATION_SYSTEM_PROMPT
        self._on_llm_complete = on_llm_complete
        self._log = structlog.get_logger(self.__class__.__module__)

    async def run(self, trigger: AgentTrigger) -> AgentResult:
        """Execute the full email-draft generation pipeline.

        Args:
            trigger: Work item from the queue containing ``client_id``,
                ``advisor_id``, and ``trigger_type``.

        Returns:
            ``AgentResult(success=True, output={"draft_id": "<uuid>"})`` on
            success.

        Raises:
            GenerationError: If the LLM provider call fails.
            NotFoundError: If the client referenced in the trigger does not
                exist.
        """
        client_id = trigger.client_id
        trigger_type = trigger.trigger_type
        force: bool = trigger.payload.get("force", False)

        log = self._log.bind(client_id=str(client_id), trigger_type=trigger_type)
        log.info("generation_agent_started")

        with _tracer.start_as_current_span("generation.pipeline") as span:
            span.set_attribute("client_id", str(client_id))
            span.set_attribute("trigger_type", trigger_type)

            existing_id = await self._draft_writer.find_pending_draft(client_id)
            if existing_id is not None:
                if not force:
                    log.info(
                        "generation_agent_skipped_existing_pending",
                        draft_id=str(existing_id),
                    )
                    span.set_attribute("draft_id", str(existing_id))
                    return AgentResult(
                        success=True,
                        trigger_type=trigger_type,
                        client_id=client_id,
                        output={"draft_id": str(existing_id), "cached": True},
                    )
                log.info(
                    "generation_agent_force_replacing", draft_id=str(existing_id)
                )
                await self._draft_writer.delete_draft(existing_id)

            ctx = await self._context_reader.assemble(client_id)
            llm_started = perf_counter()

            try:
                result = await self._provider.complete(
                    ctx.prompt_block,
                    system=self._system_prompt,
                    model=self._model,
                )
            except LLMProviderError as exc:
                log.error("generation_agent_llm_failed", error=exc.detail, exc_info=True)
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, exc.detail)
                span_ctx = span.get_span_context()
                trace_id = (
                    format(span_ctx.trace_id, "032x") if span_ctx.is_valid else None
                )
                span_id = (
                    format(span_ctx.span_id, "016x") if span_ctx.is_valid else None
                )
                if self._on_llm_complete:
                    self._on_llm_complete(self._model, "error", 0.0, None, None)
                self._fire_audit(
                    client_id=client_id,
                    prompt=ctx.prompt_block,
                    response="",
                    status="error",
                    latency_ms=0.0,
                    prompt_tokens=None,
                    completion_tokens=None,
                    error=exc.detail,
                    trace_id=trace_id,
                    span_id=span_id,
                )
                raise GenerationError(f"LLM provider failed: {exc.detail}") from exc

            llm_duration = perf_counter() - llm_started
            generated_content = _normalize(result.response)
            log.info(
                "generation_agent_llm_complete",
                model=self._model,
                latency_ms=round(result.latency_ms, 1),
                chars=len(generated_content),
            )

            span_ctx = span.get_span_context()
            trace_id = (
                format(span_ctx.trace_id, "032x") if span_ctx.is_valid else None
            )
            span_id = (
                format(span_ctx.span_id, "016x") if span_ctx.is_valid else None
            )

            if self._on_llm_complete:
                self._on_llm_complete(
                    self._model,
                    "success",
                    llm_duration,
                    result.prompt_tokens,
                    result.completion_tokens,
                )
            self._fire_audit(
                client_id=client_id,
                prompt=result.prompt,
                response=result.response,
                status="success",
                latency_ms=result.latency_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                error=None,
                trace_id=trace_id,
                span_id=span_id,
            )

            with _tracer.start_as_current_span("generation.persist") as persist_span:
                draft_id = await self._draft_writer.create_draft(
                    client_id, trigger_type, generated_content
                )
                persist_span.set_attribute("draft_id", str(draft_id))

            span.set_attribute("draft_id", str(draft_id))
            log.info("generation_agent_complete", draft_id=str(draft_id))
            return AgentResult(
                success=True,
                trigger_type=trigger_type,
                client_id=client_id,
                output={"draft_id": str(draft_id)},
            )

    def _fire_audit(
        self,
        *,
        client_id: uuid.UUID,
        prompt: str,
        response: str,
        status: str,
        latency_ms: float,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        error: str | None,
        trace_id: str | None,
        span_id: str | None,
    ) -> None:
        """Schedule a fire-and-forget audit log event."""
        if self._audit_logger is None:
            return
        event: LLMAuditEvent = make_audit_event(
            pipeline="generation",
            client_id=client_id,
            model=self._model,
            prompt=prompt,
            response=response,
            status=status,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            error=error,
            trace_id=trace_id,
            span_id=span_id,
        )
        asyncio.create_task(self._audit_logger.log(event))


def _normalize(raw: str) -> str:
    """Strip accidental artefacts from the LLM response.

    Removes subject lines, salutations, and sign-offs that the model may
    include despite system prompt instructions.  Returns the trimmed body.
    """
    text = _SUBJECT_RE.sub("", raw)
    text = _SALUTATION_RE.sub("", text)
    text = _SIGN_OFF_RE.sub("", text)
    return text.strip()
