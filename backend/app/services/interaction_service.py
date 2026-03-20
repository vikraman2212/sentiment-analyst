"""Service layer for Interaction operations."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.interaction import Interaction
from app.repositories.client import ClientRepository
from app.repositories.interaction import InteractionRepository
from app.schemas.interaction import InteractionCreate

logger = structlog.get_logger(__name__)


class InteractionService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = InteractionRepository(db)
        self._client_repo = ClientRepository(db)

    async def create(self, payload: InteractionCreate) -> Interaction:
        """Record a new interaction for a client.

        Args:
            payload: Validated interaction creation data.

        Returns:
            The newly created Interaction ORM instance.

        Raises:
            NotFoundError: If the referenced client does not exist.
        """
        log = logger.bind(client_id=str(payload.client_id))
        log.info("interaction_create_started")
        client = await self._client_repo.get_by_id(payload.client_id)
        if client is None:
            log.warning("interaction_create_client_not_found")
            raise NotFoundError(f"Client {payload.client_id} not found")
        interaction = await self._repo.create(payload)
        log.info("interaction_create_complete", interaction_id=str(interaction.id))
        return interaction

    async def list_by_client(self, client_id: uuid.UUID) -> list[Interaction]:
        """Return all interactions for the given client.

        Raises:
            NotFoundError: If the client does not exist.
        """
        log = logger.bind(client_id=str(client_id))
        log.info("interaction_list_started")
        client = await self._client_repo.get_by_id(client_id)
        if client is None:
            log.warning("interaction_list_client_not_found")
            raise NotFoundError(f"Client {client_id} not found")
        interactions = await self._repo.list_by_client(client_id)
        log.info("interaction_list_complete", count=len(interactions))
        return interactions
