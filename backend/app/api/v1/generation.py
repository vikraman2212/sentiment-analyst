"""GET /api/v1/generation/failures — generation failure inspection endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.repositories.generation_failure import GenerationFailureRepository
from app.schemas.generation import GenerationFailureResponse

router = APIRouter(tags=["generation"])


@router.get(
    "/generation/failures",
    response_model=list[GenerationFailureResponse],
)
async def list_generation_failures(
    db: AsyncSession = Depends(get_db),
) -> list[GenerationFailureResponse]:
    """Return all unresolved generation failure records (dead-letter queue).

    Failures are persisted when ``GenerationWorker`` cannot process a
    queue message after all retry attempts.  Operators use this endpoint
    to inspect and triage stuck or failed jobs.
    """
    repo = GenerationFailureRepository(db)
    failures = await repo.list_unresolved()
    return [GenerationFailureResponse.model_validate(f) for f in failures]
