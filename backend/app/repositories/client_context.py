"""Repository for ClientContext operations."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_context import ClientContext
from app.schemas.client_context import ClientContextCreate

logger = structlog.get_logger(__name__)


class ClientContextRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_client(self, client_id: uuid.UUID) -> list[ClientContext]:
        """Return all context tags for the given client."""
        result = await self._db.execute(
            select(ClientContext)
            .where(ClientContext.client_id == client_id)
            .order_by(ClientContext.category)
        )
        return list(result.scalars().all())

    async def create(self, payload: ClientContextCreate) -> ClientContext:
        """Persist a new context tag and return the hydrated instance."""
        context = ClientContext(**payload.model_dump())
        self._db.add(context)
        await self._db.commit()
        await self._db.refresh(context)
        return context

    async def bulk_create(
        self, payloads: list[ClientContextCreate]
    ) -> list[ClientContext]:
        """Persist multiple context tags in a single transaction.

        Args:
            payloads: List of tag creation payloads.

        Returns:
            List of hydrated ClientContext instances.
        """
        contexts = [ClientContext(**p.model_dump()) for p in payloads]
        self._db.add_all(contexts)
        await self._db.commit()
        for ctx in contexts:
            await self._db.refresh(ctx)
        return contexts

    async def delete(self, context: ClientContext) -> None:
        """Delete the context tag record."""
        await self._db.delete(context)
        await self._db.commit()
