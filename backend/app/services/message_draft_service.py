"""Service layer for MessageDraft operations."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.message_draft import MessageDraft
from app.repositories.client import ClientRepository
from app.repositories.message_draft import MessageDraftRepository
from app.schemas.message_draft import MessageDraftCreate, MessageDraftStatusUpdate

logger = structlog.get_logger(__name__)


class MessageDraftService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = MessageDraftRepository(db)
        self._client_repo = ClientRepository(db)

    async def create(self, payload: MessageDraftCreate) -> MessageDraft:
        """Create a new message draft for a client.

        Args:
            payload: Validated draft creation data.

        Returns:
            The newly created MessageDraft ORM instance.

        Raises:
            NotFoundError: If the referenced client does not exist.
        """
        log = logger.bind(client_id=str(payload.client_id))
        log.info("message_draft_create_started")
        client = await self._client_repo.get_by_id(payload.client_id)
        if client is None:
            log.warning("message_draft_create_client_not_found")
            raise NotFoundError(f"Client {payload.client_id} not found")
        draft = await self._repo.create(payload)
        log.info("message_draft_create_complete", draft_id=str(draft.id))
        return draft

    async def list_by_client(self, client_id: uuid.UUID) -> list[MessageDraft]:
        """Return all drafts for the given client.

        Raises:
            NotFoundError: If the client does not exist.
        """
        log = logger.bind(client_id=str(client_id))
        log.info("message_draft_list_started")
        client = await self._client_repo.get_by_id(client_id)
        if client is None:
            log.warning("message_draft_list_client_not_found")
            raise NotFoundError(f"Client {client_id} not found")
        drafts = await self._repo.list_by_client(client_id)
        log.info("message_draft_list_complete", count=len(drafts))
        return drafts

    async def update_status(
        self, draft_id: uuid.UUID, payload: MessageDraftStatusUpdate
    ) -> MessageDraft:
        """Update the status of a message draft.

        Raises:
            NotFoundError: If the draft does not exist.
        """
        log = logger.bind(draft_id=str(draft_id))
        log.info("message_draft_status_update_started", new_status=payload.status)
        draft = await self._repo.get_by_id(draft_id)
        if draft is None:
            log.warning("message_draft_not_found")
            raise NotFoundError(f"MessageDraft {draft_id} not found")
        updated = await self._repo.update_status(draft, payload)
        log.info("message_draft_status_update_complete")
        return updated
