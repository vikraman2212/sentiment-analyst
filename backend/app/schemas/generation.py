"""Pydantic schemas for the email generation pipeline."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GenerationFailureResponse(BaseModel):
    """Response schema for dead-letter generation failure records."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    trigger_type: str
    message_id: str
    error_detail: str
    failed_at: datetime
    resolved: bool
