"""Pydantic schemas for the email generation pipeline."""

import uuid

from pydantic import BaseModel, ConfigDict


class GenerateRequest(BaseModel):
    client_id: uuid.UUID
    trigger_type: str = "review_due"
    force: bool = False


class GenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    draft_id: uuid.UUID
    client_id: uuid.UUID
    trigger_type: str
    generated_content: str
