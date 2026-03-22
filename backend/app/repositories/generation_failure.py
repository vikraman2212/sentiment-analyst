"""Repository for GenerationFailure dead-letter records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation_failure import GenerationFailure


class GenerationFailureRepository:
    """Encapsulates all database access for GenerationFailure records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        client_id: uuid.UUID,
        trigger_type: str,
        message_id: str,
        error_detail: str,
    ) -> GenerationFailure:
        """Persist a new dead-letter failure record and return it.

        Args:
            client_id: UUID of the client the failed job was for.
            trigger_type: Trigger label from the original queue message.
            message_id: Queue message ID for correlation.
            error_detail: String representation of the exception.

        Returns:
            The persisted ``GenerationFailure`` ORM instance.
        """
        failure = GenerationFailure(
            client_id=client_id,
            trigger_type=trigger_type,
            message_id=message_id,
            error_detail=error_detail,
        )
        self._db.add(failure)
        await self._db.commit()
        await self._db.refresh(failure)
        return failure

    async def list_unresolved(self) -> list[GenerationFailure]:
        """Return all unresolved failure records, ordered by most recent first.

        Returns:
            List of ``GenerationFailure`` instances where ``resolved`` is False.
        """
        result = await self._db.execute(
            select(GenerationFailure)
            .where(GenerationFailure.resolved.is_(False))
            .order_by(GenerationFailure.failed_at.desc())
        )
        return list(result.scalars().all())
