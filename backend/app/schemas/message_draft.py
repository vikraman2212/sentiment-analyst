import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.client_context import ClientContextResponse

DraftStatus = Literal["pending", "sent"]


class MessageDraftCreate(BaseModel):
    client_id: uuid.UUID
    trigger_type: str
    generated_content: str


class MessageDraftStatusUpdate(BaseModel):
    status: DraftStatus


class MessageDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    trigger_type: str
    generated_content: str
    status: str


class PendingDraftResponse(BaseModel):
    """Response schema for the pending drafts inbox endpoint."""

    draft_id: uuid.UUID
    client_name: str
    trigger_type: str
    generated_content: str
    context_used: list[ClientContextResponse]
