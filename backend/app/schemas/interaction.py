import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InteractionCreate(BaseModel):
    client_id: uuid.UUID
    type: str = "voice_memo"
    raw_transcript: str | None = None


class InteractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    type: str
    raw_transcript: str | None
    created_at: datetime
