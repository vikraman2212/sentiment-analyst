"""Repository for Client CRUD operations."""

import uuid
from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate

logger = structlog.get_logger(__name__)


class ClientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, client_id: uuid.UUID) -> Client | None:
        """Return the client with the given id, or None."""
        result = await self._db.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Client]:
        """Return every client ordered by last/first name."""
        result = await self._db.execute(
            select(Client).order_by(Client.last_name, Client.first_name)
        )
        return list(result.scalars().all())

    async def list_by_advisor(self, advisor_id: uuid.UUID) -> list[Client]:
        """Return all clients belonging to the given advisor."""
        result = await self._db.execute(
            select(Client)
            .where(Client.advisor_id == advisor_id)
            .order_by(Client.last_name, Client.first_name)
        )
        return list(result.scalars().all())

    async def list_needing_review(
        self, advisor_id: uuid.UUID, cutoff: date
    ) -> list[Client]:
        """Return clients whose next review date is on or before the cutoff.

        Clients without a next_review_date are excluded silently.

        Args:
            advisor_id: Filter to this advisor's clients.
            cutoff: Upper bound for next_review_date (inclusive).

        Returns:
            Clients ordered by next_review_date ascending.
        """
        result = await self._db.execute(
            select(Client)
            .where(
                Client.advisor_id == advisor_id,
                Client.next_review_date.isnot(None),
                Client.next_review_date <= cutoff,
            )
            .order_by(Client.next_review_date)
        )
        return list(result.scalars().all())

    async def find_by_name(
        self, advisor_id: uuid.UUID, first_name: str, last_name: str
    ) -> Client | None:
        """Return an existing client matching advisor + full name, or None."""
        result = await self._db.execute(
            select(Client).where(
                Client.advisor_id == advisor_id,
                Client.first_name == first_name,
                Client.last_name == last_name,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, payload: ClientCreate) -> Client:
        """Persist a new client and return the hydrated instance."""
        client = Client(**payload.model_dump())
        self._db.add(client)
        await self._db.commit()
        await self._db.refresh(client)
        return client

    async def update(self, client: Client, payload: ClientUpdate) -> Client:
        """Apply non-None fields from payload to client and persist."""
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(client, field, value)
        await self._db.commit()
        await self._db.refresh(client)
        return client

    async def delete(self, client: Client) -> None:
        """Delete the client record."""
        await self._db.delete(client)
        await self._db.commit()
