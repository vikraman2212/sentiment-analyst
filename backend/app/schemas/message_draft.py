import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

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
