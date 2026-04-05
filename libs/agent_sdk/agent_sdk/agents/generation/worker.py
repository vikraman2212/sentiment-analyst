"""Generation worker — queue consumer for the email draft generation agent.

Subclasses ``BaseQueueWorker`` from the SDK.  The base class owns the async
consumer loop, OTEL span creation, and W3C trace-context propagation.  This
class contributes only the generation-specific wiring:

- ``_handle()`` — builds a ``GenerationAgent`` from injected factories,
  invokes it per message, and fires the optional telemetry callback.
- ``_on_failure()`` — invokes the optional dead-letter callback so the
  caller (backend) can persist to its own failure table.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import TYPE_CHECKING

import structlog

from agent_sdk.agents.generation.ports import IContextAssembler, IDraftWriter
from agent_sdk.agents.generation.service import GenerationAgent
from agent_sdk.core.contracts import AgentTrigger
from agent_sdk.core.exceptions import GenerationError
from agent_sdk.core.llm_provider import LLMProvider
from agent_sdk.core.message_queue import GenerationMessage, MessageQueue
from agent_sdk.core.session import IAsyncSession, ISessionFactory
from agent_sdk.orchestration.worker import BaseQueueWorker

if TYPE_CHECKING:
    from agent_sdk.audit.logger import AbstractAuditLogger

logger = structlog.get_logger(__name__)


class GenerationWorker(BaseQueueWorker):
    """Queue consumer wired to the ``GenerationAgent`` pipeline.

    All backend-specific I/O (DB session, context assembly, draft writing,
    failure persistence, Prometheus metrics) is supplied via constructor
    injection so the worker can be instantiated and tested without the
    backend application context.

    Args:
        queue: Queue from which ``GenerationMessage`` objects are consumed.
        session_factory: Async-context-manager factory that yields a session
            compatible with ``IAsyncSession``.
        context_reader_factory: Callable that accepts a session and returns an
            ``IContextAssembler`` implementation.
        draft_writer_factory: Callable that accepts a session and returns an
            ``IDraftWriter`` implementation.
        provider: LLM provider forwarded to each ``GenerationAgent`` instance.
        audit_logger: Optional audit logger forwarded to each agent.
        generation_model: Model identifier forwarded to each agent.
        system_prompt: Optional system prompt override forwarded to each agent.
        on_run_complete: Optional callback invoked after each message with
            ``(status: str, duration_seconds: float)``.  Use for Prometheus
            counters without coupling the SDK to a metrics library.
        on_failure: Optional async callback invoked when a message fails all
            retries with ``(message, exception)``.  Use for dead-letter
            persistence without importing backend repositories here.
    """

    def __init__(
        self,
        queue: MessageQueue,
        session_factory: ISessionFactory,
        context_reader_factory: Callable[[IAsyncSession], IContextAssembler],
        draft_writer_factory: Callable[[IAsyncSession], IDraftWriter],
        provider: LLMProvider | None = None,
        audit_logger: AbstractAuditLogger | None = None,
        generation_model: str = "llama3.2",
        system_prompt: str | None = None,
        on_run_complete: Callable[[str, float], None] | None = None,
        on_failure: (
            Callable[[GenerationMessage, Exception], Awaitable[None]] | None
        ) = None,
        on_llm_complete: (
            Callable[[str, str, float, int | None, int | None], None] | None
        ) = None,
    ) -> None:
        super().__init__(queue=queue, session_factory=session_factory)
        self._context_reader_factory = context_reader_factory
        self._draft_writer_factory = draft_writer_factory
        self._provider = provider
        self._audit_logger = audit_logger
        self._generation_model = generation_model
        self._system_prompt = system_prompt
        self._on_run_complete = on_run_complete
        self._on_failure_cb = on_failure
        self._on_llm_complete = on_llm_complete

    async def _handle(
        self,
        message: GenerationMessage,
        session: IAsyncSession,
    ) -> None:
        """Build and run a ``GenerationAgent`` for the given message.

        Args:
            message: The generation work item from the queue.
            session: Active async session for this message lifecycle.
        """
        started_at = perf_counter()
        status = "error"
        log = logger.bind(
            client_id=str(message.client_id),
            message_id=message.message_id,
            trigger_type=message.trigger_type,
        )
        log.info("generation_worker_processing")

        try:
            if self._provider is None:
                raise GenerationError("No LLM provider configured for GenerationWorker")

            agent = GenerationAgent(
                context_reader=self._context_reader_factory(session),
                draft_writer=self._draft_writer_factory(session),
                provider=self._provider,
                audit_logger=self._audit_logger,
                generation_model=self._generation_model,
                system_prompt=self._system_prompt,
                on_llm_complete=self._on_llm_complete,
            )
            result = await agent.run(
                AgentTrigger(
                    client_id=message.client_id,
                    advisor_id=message.advisor_id,
                    trigger_type=message.trigger_type,
                )
            )
            if not result.success:
                raise GenerationError(result.error or "GenerationAgent returned failure")
            log.info(
                "generation_worker_success",
                draft_id=result.output.get("draft_id"),
            )
            status = "success"
        except Exception:
            raise  # BaseQueueWorker._consume_loop() catches and calls _on_failure
        finally:
            if self._on_run_complete:
                self._on_run_complete(status, perf_counter() - started_at)

    async def _on_failure(
        self,
        message: GenerationMessage,
        error: Exception,
    ) -> None:
        """Invoke the dead-letter callback if configured.

        Swallows any exception raised by the callback so the consumer loop
        is never interrupted by a secondary failure.

        Args:
            message: The message that caused the failure.
            error: The exception raised by ``_handle()``.
        """
        log = logger.bind(
            client_id=str(message.client_id),
            message_id=message.message_id,
        )
        log.error(
            "generation_worker_failed",
            error=str(error),
            exc_info=True,
        )
        if self._on_failure_cb is not None:
            try:
                await self._on_failure_cb(message, error)
            except Exception as cb_exc:  # noqa: BLE001
                log.error(
                    "generation_worker_on_failure_callback_error",
                    error=str(cb_exc),
                    exc_info=True,
                )
