"""Concrete adaptor implementations of the generation agent's SDK ports.

These classes translate between the SDK's protocol interfaces
(``IContextAssembler``, ``IDraftWriter``, ``IClientSource``) and the
backend's SQLAlchemy-coupled services and repositories.

They live here — not in the SDK — because they depend on ORM models,
repos, and backend schemas.
"""

from __future__ import annotations

import uuid

import structlog
from agent_sdk.agents.generation.ports import (
    IClientSource,
    IContextAssembler,
    IDraftWriter,
    PromptContext,
)

from app.repositories.advisor import AdvisorRepository
from app.schemas.message_draft import MessageDraftCreate
from app.services.context_assembly import ContextAssemblyService
from app.services.message_draft_service import MessageDraftService

logger = structlog.get_logger(__name__)


class ContextAssemblyAdaptor:
    """Wraps ``ContextAssemblyService`` to satisfy ``IContextAssembler``.

    Extracts only the ``prompt_block`` and ``client_name`` fields from the
    fuller ``AssembledContext`` returned by the backend service.
    """

    def __init__(self, db: object) -> None:
        self._svc = ContextAssemblyService(db)  # type: ignore[arg-type]

    async def assemble(self, client_id: uuid.UUID) -> PromptContext:
        """Assemble the prompt context for the given client.

        Args:
            client_id: UUID of the target client.

        Returns:
            ``PromptContext`` with prompt_block and client_name.

        Raises:
            NotFoundError: If the client does not exist.
        """
        ctx = await self._svc.assemble(client_id)
        return PromptContext(
            prompt_block=ctx.prompt_block,
            client_name=ctx.client_name,
        )


# Verify protocol satisfaction at import time.
assert isinstance(ContextAssemblyAdaptor.__new__(ContextAssemblyAdaptor), IContextAssembler)  # type: ignore[arg-type]


class MessageDraftAdaptor:
    """Wraps ``MessageDraftService`` to satisfy ``IDraftWriter``.

    Translates between the SDK's primitive-typed interface and the
    backend's Pydantic-schema-based service API.
    """

    def __init__(self, db: object) -> None:
        self._svc = MessageDraftService(db)  # type: ignore[arg-type]

    async def find_pending_draft(self, client_id: uuid.UUID) -> uuid.UUID | None:
        """Return the ID of an existing pending draft, or None."""
        draft = await self._svc.find_pending_by_client(client_id)
        return draft.id if draft is not None else None

    async def create_draft(
        self, client_id: uuid.UUID, trigger_type: str, content: str
    ) -> uuid.UUID:
        """Create a new pending draft and return its UUID."""
        draft = await self._svc.create(
            MessageDraftCreate(
                client_id=client_id,
                trigger_type=trigger_type,
                generated_content=content,
            )
        )
        return draft.id

    async def delete_draft(self, draft_id: uuid.UUID) -> None:
        """Delete a draft by ID."""
        await self._svc.delete(draft_id)


assert isinstance(MessageDraftAdaptor.__new__(MessageDraftAdaptor), IDraftWriter)  # type: ignore[arg-type]


class EligibleClientSource:
    """Satisfies ``IClientSource`` using ``AdvisorRepository`` and ``ContextAssemblyService``.

    Iterates all advisors and collects the client IDs whose context tags
    indicate a review is due.
    """

    async def get_eligible_clients(
        self, session: object
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """Return (client_id, advisor_id) pairs needing generation.

        Args:
            session: Active async DB session from the SDK session factory.

        Returns:
            List of (client_id, advisor_id) pairs.  Empty when no clients
            are eligible.
        """
        log = logger.bind(job="get_eligible_clients")
        advisor_repo = AdvisorRepository(session)  # type: ignore[arg-type]
        advisors = await advisor_repo.list_all()

        if not advisors:
            log.info("eligible_clients_no_advisors")
            return []

        pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
        for advisor in advisors:
            context_svc = ContextAssemblyService(session)  # type: ignore[arg-type]
            try:
                contexts = await context_svc.list_needing_review(advisor.id)
            except Exception as exc:
                log.error(
                    "eligible_clients_advisor_failed",
                    advisor_id=str(advisor.id),
                    error=str(exc),
                    exc_info=True,
                )
                continue
            for ctx in contexts:
                pairs.append((ctx.client_id, advisor.id))

        return pairs


assert isinstance(EligibleClientSource(), IClientSource)
