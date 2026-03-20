"""Service layer for Advisor operations."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.advisor import Advisor
from app.repositories.advisor import AdvisorRepository
from app.schemas.advisor import AdvisorCreate, AdvisorUpdate

logger = structlog.get_logger(__name__)


class AdvisorService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = AdvisorRepository(db)

    async def create(self, payload: AdvisorCreate) -> Advisor:
        """Create a new advisor, enforcing email uniqueness.

        Args:
            payload: Validated advisor creation data.

        Returns:
            The newly created Advisor ORM instance.

        Raises:
            ConflictError: If an advisor with the same email already exists.
        """
        log = logger.bind(email_domain=payload.email.split("@")[-1])
        log.info("advisor_create_started")
        existing = await self._repo.get_by_email(payload.email)
        if existing:
            log.warning("advisor_create_duplicate")
            raise ConflictError("An advisor with this email already exists")
        advisor = await self._repo.create(payload)
        log.info("advisor_create_complete", advisor_id=str(advisor.id))
        return advisor

    async def get(self, advisor_id: uuid.UUID) -> Advisor:
        """Fetch an advisor by id.

        Raises:
            NotFoundError: If no advisor exists with the given id.
        """
        log = logger.bind(advisor_id=str(advisor_id))
        log.info("advisor_get_started")
        advisor = await self._repo.get_by_id(advisor_id)
        if advisor is None:
            log.warning("advisor_not_found")
            raise NotFoundError(f"Advisor {advisor_id} not found")
        log.info("advisor_get_complete")
        return advisor

    async def list_all(self) -> list[Advisor]:
        """Return all advisors."""
        logger.info("advisor_list_started")
        advisors = await self._repo.list_all()
        logger.info("advisor_list_complete", count=len(advisors))
        return advisors

    async def update(self, advisor_id: uuid.UUID, payload: AdvisorUpdate) -> Advisor:
        """Update an advisor's mutable fields.

        Raises:
            NotFoundError: If no advisor exists with the given id.
        """
        advisor = await self.get(advisor_id)
        log = logger.bind(advisor_id=str(advisor_id))
        log.info("advisor_update_started")
        updated = await self._repo.update(advisor, payload)
        log.info("advisor_update_complete")
        return updated

    async def delete(self, advisor_id: uuid.UUID) -> None:
        """Delete an advisor and cascade their clients.

        Raises:
            NotFoundError: If no advisor exists with the given id.
        """
        advisor = await self.get(advisor_id)
        log = logger.bind(advisor_id=str(advisor_id))
        log.info("advisor_delete_started")
        await self._repo.delete(advisor)
        log.info("advisor_delete_complete")
