import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.schemas.interaction import InteractionCreate, InteractionResponse
from app.services.interaction_service import InteractionService

router = APIRouter(tags=["interactions"])


@router.post(
    "/interactions/",
    response_model=InteractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_interaction(
    payload: InteractionCreate,
    db: AsyncSession = Depends(get_db),
) -> InteractionResponse:
    return await InteractionService(db).create(payload)


@router.get(
    "/clients/{client_id}/interactions",
    response_model=list[InteractionResponse],
)
async def list_client_interactions(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[InteractionResponse]:
    return await InteractionService(db).list_by_client(client_id)
