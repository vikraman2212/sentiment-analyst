"""POST /api/v1/generate — email draft generation endpoint."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.schemas.generation import GenerateRequest, GenerateResponse
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
