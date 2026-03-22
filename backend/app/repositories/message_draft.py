"""Repository for MessageDraft operations."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import Client
from app.models.message_draft import MessageDraft
from app.schemas.message_draft import MessageDraftCreate, MessageDraftStatusUpdate

logger = structlog.get_logger(__name__)


class MessageDraftRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, draft_id: uuid.UUID) -> MessageDraft | None:
        """Return the message draft with the given id, or None."""
        result = await self._db.execute(
            select(MessageDraft).where(MessageDraft.id == draft_id)
        )
        return result.scalar_one_or_none()

    async def list_by_client(self, client_id: uuid.UUID) -> list[MessageDraft]:
        """Return all drafts for the given client, newest first."""
        result = await self._db.execute(
            select(MessageDraft).where(MessageDraft.client_id == client_id)
        )
        return list(result.scalars().all())

    async def list_all_pending(self) -> list[MessageDraft]:
        """Return all pending drafts with client and context tags eager-loaded."""
        result = await self._db.execute(
            select(MessageDraft)
            .where(MessageDraft.status == "pending")
            .options(
                selectinload(MessageDraft.client).selectinload(Client.context_tags)
            )
        )
        return list(result.scalars().all())

    async def create(self, payload: MessageDraftCreate) -> MessageDraft:
        """Persist a new draft and return the hydrated instance."""
        draft = MessageDraft(**payload.model_dump())
        self._db.add(draft)
        await self._db.commit()
        await self._db.refresh(draft)
        return draft

    async def find_pending_by_client(self, client_id: uuid.UUID) -> MessageDraft | None:
        """Return the single pending draft for the given client, or None."""
        result = await self._db.execute(
            select(MessageDraft).where(
                MessageDraft.client_id == client_id,
                MessageDraft.status == "pending",
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, draft: MessageDraft) -> None:
        """Permanently delete the given draft row."""
        await self._db.delete(draft)
        await self._db.commit()

    async def update_status(
        self, draft: MessageDraft, payload: MessageDraftStatusUpdate
    ) -> MessageDraft:
        """Update the draft status and persist."""
        draft.status = payload.status
        await self._db.commit()
        await self._db.refresh(draft)
        return draft
