"""POST /api/v1/generate — email draft generation endpoint."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.repositories.generation_failure import GenerationFailureRepository
from app.schemas.generation import GenerateRequest, GenerateResponse, GenerationFailureResponse
from app.services.generation_service import GenerationService

router = APIRouter(tags=["generation"])


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_draft(
    payload: GenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Generate a personalised draft email for a client and persist it.

    Uses the client's financial profile and context tags to prompt the
    configured LLM.  Returns the persisted draft id and generated content.
    """
    draft = await GenerationService(db).generate(
        client_id=payload.client_id,
        trigger_type=payload.trigger_type,
        force=payload.force,
    )
    return GenerateResponse(
        draft_id=draft.id,
        client_id=draft.client_id,
        trigger_type=draft.trigger_type,
        generated_content=draft.generated_content,
    )


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
