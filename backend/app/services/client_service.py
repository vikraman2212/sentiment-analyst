"""Service layer for Client operations."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.client import Client
from app.repositories.advisor import AdvisorRepository
from app.repositories.client import ClientRepository
from app.schemas.client import ClientCreate, ClientListItem, ClientUpdate

logger = structlog.get_logger(__name__)


class ClientService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = ClientRepository(db)
        self._advisor_repo = AdvisorRepository(db)

    async def create(self, payload: ClientCreate) -> Client:
        """Create a new client under a given advisor.

        Args:
            payload: Validated client creation data.

        Returns:
            The newly created Client ORM instance.

        Raises:
            NotFoundError: If the referenced advisor does not exist.
            ConflictError: If a client with the same name already exists for this advisor.
        """
        log = logger.bind(advisor_id=str(payload.advisor_id))
        log.info("client_create_started")
        advisor = await self._advisor_repo.get_by_id(payload.advisor_id)
        if advisor is None:
            log.warning("client_create_advisor_not_found")
            raise NotFoundError(f"Advisor {payload.advisor_id} not found")
        existing = await self._repo.find_by_name(
            payload.advisor_id, payload.first_name, payload.last_name
        )
        if existing:
            log.warning("client_create_duplicate")
            raise ConflictError("A client with this name already exists for this advisor")
        client = await self._repo.create(payload)
        log.info("client_create_complete", client_id=str(client.id))
        return client

    async def get(self, client_id: uuid.UUID) -> Client:
        """Fetch a client by id.

        Raises:
            NotFoundError: If no client exists with the given id.
        """
        log = logger.bind(client_id=str(client_id))
        log.info("client_get_started")
        client = await self._repo.get_by_id(client_id)
        if client is None:
            log.warning("client_not_found")
            raise NotFoundError(f"Client {client_id} not found")
        log.info("client_get_complete")
        return client

    async def list(self, advisor_id: uuid.UUID | None) -> list[ClientListItem]:
        """Return clients scoped to an advisor, or all clients if advisor_id is None.

        Args:
            advisor_id: Optional UUID to filter by advisor.

        Returns:
            List of ClientListItem projections.

        Raises:
            NotFoundError: If advisor_id is provided but the advisor does not exist.
        """
        log = logger.bind(advisor_id=str(advisor_id) if advisor_id else "all")
        log.info("client_list_started")
        if advisor_id is not None:
            advisor = await self._advisor_repo.get_by_id(advisor_id)
            if advisor is None:
                log.warning("client_list_advisor_not_found")
                raise NotFoundError(f"Advisor {advisor_id} not found")
            clients = await self._repo.list_by_advisor(advisor_id)
        else:
            clients = await self._repo.list_all()
        log.info("client_list_complete", count=len(clients))
        return [ClientListItem.model_validate(c) for c in clients]

    async def list_by_advisor(self, advisor_id: uuid.UUID) -> list[Client]:
        """Return all clients for the given advisor.

        Raises:
            NotFoundError: If the advisor does not exist.
        """
        log = logger.bind(advisor_id=str(advisor_id))
        log.info("client_list_started")
        advisor = await self._advisor_repo.get_by_id(advisor_id)
        if advisor is None:
            log.warning("client_list_advisor_not_found")
            raise NotFoundError(f"Advisor {advisor_id} not found")
        clients = await self._repo.list_by_advisor(advisor_id)
        log.info("client_list_complete", count=len(clients))
        return clients

    async def update(self, client_id: uuid.UUID, payload: ClientUpdate) -> Client:
        """Update a client's mutable fields.

        Raises:
            NotFoundError: If no client exists with the given id.
        """
        client = await self.get(client_id)
        log = logger.bind(client_id=str(client_id))
        log.info("client_update_started")
        updated = await self._repo.update(client, payload)
        log.info("client_update_complete")
        return updated

    async def delete(self, client_id: uuid.UUID) -> None:
        """Delete a client and cascade all related data.

        Raises:
            NotFoundError: If no client exists with the given id.
        """
        client = await self.get(client_id)
        log = logger.bind(client_id=str(client_id))
        log.info("client_delete_started")
        await self._repo.delete(client)
        log.info("client_delete_complete")
