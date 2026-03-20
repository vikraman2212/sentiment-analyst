"""Repository for Advisor CRUD operations."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.advisor import Advisor
from app.schemas.advisor import AdvisorCreate, AdvisorUpdate

logger = structlog.get_logger(__name__)


class AdvisorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, advisor_id: uuid.UUID) -> Advisor | None:
        """Return the advisor with the given id, or None."""
        result = await self._db.execute(
            select(Advisor).where(Advisor.id == advisor_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Advisor | None:
        """Return the advisor matching the email, or None."""
        result = await self._db.execute(
            select(Advisor).where(Advisor.email == email)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Advisor]:
        """Return all advisors ordered by full_name."""
        result = await self._db.execute(select(Advisor).order_by(Advisor.full_name))
        return list(result.scalars().all())

    async def create(self, payload: AdvisorCreate) -> Advisor:
        """Persist a new advisor and return the hydrated instance."""
        advisor = Advisor(**payload.model_dump())
        self._db.add(advisor)
        await self._db.commit()
        await self._db.refresh(advisor)
        return advisor

    async def update(self, advisor: Advisor, payload: AdvisorUpdate) -> Advisor:
        """Apply non-None fields from payload to advisor and persist."""
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(advisor, field, value)
        await self._db.commit()
        await self._db.refresh(advisor)
        return advisor

    async def delete(self, advisor: Advisor) -> None:
        """Delete the advisor record."""
        await self._db.delete(advisor)
        await self._db.commit()
