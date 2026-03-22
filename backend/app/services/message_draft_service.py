"""Service layer for MessageDraft operations."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.message_draft import MessageDraft
from app.repositories.client import ClientRepository
from app.repositories.message_draft import MessageDraftRepository
from app.schemas.client_context import ClientContextResponse
from app.schemas.message_draft import MessageDraftCreate, MessageDraftStatusUpdate, PendingDraftResponse

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

    async def list_all_pending(self) -> list[PendingDraftResponse]:
        """Return all pending drafts across all clients for the inbox.

        Returns:
            List of PendingDraftResponse containing draft metadata, client
            name, and the context snippets associated with the client.
        """
        logger.info("message_draft_list_all_pending_started")
        drafts = await self._repo.list_all_pending()
        result = [
            PendingDraftResponse(
                draft_id=draft.id,
                client_name=f"{draft.client.first_name} {draft.client.last_name}",
                trigger_type=draft.trigger_type,
                generated_content=draft.generated_content,
                context_used=[
                    ClientContextResponse.model_validate(tag, from_attributes=True)
                    for tag in draft.client.context_tags
                ],
            )
            for draft in drafts
        ]
        logger.info("message_draft_list_all_pending_complete", count=len(result))
        return result

    async def find_pending_by_client(self, client_id: uuid.UUID) -> MessageDraft | None:
        """Return the pending draft for the given client, or None.

        Args:
            client_id: Client to look up.

        Returns:
            The pending ``MessageDraft`` instance, or ``None`` if none exists.
        """
        log = logger.bind(client_id=str(client_id))
        log.info("message_draft_find_pending_started")
        draft = await self._repo.find_pending_by_client(client_id)
        log.info("message_draft_find_pending_complete", found=draft is not None)
        return draft

    async def delete(self, draft_id: uuid.UUID) -> None:
        """Permanently delete a message draft.

        Args:
            draft_id: ID of the draft to delete.

        Raises:
            NotFoundError: If the draft does not exist.
        """
        log = logger.bind(draft_id=str(draft_id))
        log.info("message_draft_delete_started")
        draft = await self._repo.get_by_id(draft_id)
        if draft is None:
            log.warning("message_draft_not_found")
            raise NotFoundError(f"MessageDraft {draft_id} not found")
        await self._repo.delete(draft)
        log.info("message_draft_delete_complete")

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
