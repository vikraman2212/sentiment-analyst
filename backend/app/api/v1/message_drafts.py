import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.schemas.message_draft import (
    MessageDraftCreate,
    MessageDraftResponse,
    MessageDraftStatusUpdate,
    PendingDraftResponse,
)
from app.services.message_draft_service import MessageDraftService

router = APIRouter(tags=["message-drafts"])


@router.get(
    "/drafts/pending",
    response_model=list[PendingDraftResponse],
)
async def list_pending_drafts(
    db: AsyncSession = Depends(get_db),
) -> list[PendingDraftResponse]:
    return await MessageDraftService(db).list_all_pending()


@router.post(
    "/message-drafts/",
    response_model=MessageDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message_draft(
    payload: MessageDraftCreate,
    db: AsyncSession = Depends(get_db),
) -> MessageDraftResponse:
    return MessageDraftResponse.model_validate(await MessageDraftService(db).create(payload))


@router.get(
    "/clients/{client_id}/message-drafts",
    response_model=list[MessageDraftResponse],
)
async def list_client_message_drafts(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[MessageDraftResponse]:
    drafts = await MessageDraftService(db).list_by_client(client_id)
    return [MessageDraftResponse.model_validate(d) for d in drafts]


@router.patch(
    "/message-drafts/{draft_id}/status",
    response_model=MessageDraftResponse,
)
async def update_draft_status(
    draft_id: uuid.UUID,
    payload: MessageDraftStatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> MessageDraftResponse:
    updated = await MessageDraftService(db).update_status(draft_id, payload)
    return MessageDraftResponse.model_validate(updated)
