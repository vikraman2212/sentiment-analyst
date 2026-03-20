import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class ClientListItem(BaseModel):
    """Lightweight projection used by the Flutter dropdown."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str


class ClientCreate(BaseModel):
    first_name: str
    last_name: str
    advisor_id: uuid.UUID
    next_review_date: date | None = None


class ClientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    next_review_date: date | None = None


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    advisor_id: uuid.UUID
    first_name: str
    last_name: str
    next_review_date: date | None
