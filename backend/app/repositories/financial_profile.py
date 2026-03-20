"""Repository for FinancialProfile upsert operations."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_profile import FinancialProfile
from app.schemas.financial_profile import FinancialProfileCreate, FinancialProfileUpdate

logger = structlog.get_logger(__name__)


class FinancialProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_client_id(self, client_id: uuid.UUID) -> FinancialProfile | None:
        """Return the financial profile for the given client, or None."""
        result = await self._db.execute(
            select(FinancialProfile).where(FinancialProfile.client_id == client_id)
        )
        return result.scalar_one_or_none()

    async def create(self, payload: FinancialProfileCreate) -> FinancialProfile:
        """Persist a new financial profile and return the hydrated instance."""
        profile = FinancialProfile(**payload.model_dump())
        self._db.add(profile)
        await self._db.commit()
        await self._db.refresh(profile)
        return profile

    async def update(
        self, profile: FinancialProfile, payload: FinancialProfileUpdate
    ) -> FinancialProfile:
        """Apply non-None fields from payload to profile and persist."""
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(profile, field, value)
        await self._db.commit()
        await self._db.refresh(profile)
        return profile
