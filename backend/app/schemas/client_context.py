import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

ContextCategory = Literal[
    "personal_interest", "financial_goal", "family_event", "risk_tolerance"
]


class ClientContextCreate(BaseModel):
    client_id: uuid.UUID
    category: ContextCategory
    content: str
    source_interaction_id: uuid.UUID | None = None


class ClientContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    category: str
    content: str
    source_interaction_id: uuid.UUID | None
