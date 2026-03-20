"""Repository for Interaction operations."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction
from app.schemas.interaction import InteractionCreate

logger = structlog.get_logger(__name__)


class InteractionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, interaction_id: uuid.UUID) -> Interaction | None:
        """Return the interaction with the given id, or None."""
        result = await self._db.execute(
            select(Interaction).where(Interaction.id == interaction_id)
        )
        return result.scalar_one_or_none()

    async def list_by_client(self, client_id: uuid.UUID) -> list[Interaction]:
        """Return all interactions for the given client, newest first."""
        result = await self._db.execute(
            select(Interaction)
            .where(Interaction.client_id == client_id)
            .order_by(Interaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, payload: InteractionCreate) -> Interaction:
        """Persist a new interaction and return the hydrated instance."""
        interaction = Interaction(**payload.model_dump())
        self._db.add(interaction)
        await self._db.commit()
        await self._db.refresh(interaction)
        return interaction
