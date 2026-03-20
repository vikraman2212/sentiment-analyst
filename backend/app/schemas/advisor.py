import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class AdvisorCreate(BaseModel):
    full_name: str
    email: EmailStr
    default_tone: str = "professional"


class AdvisorUpdate(BaseModel):
    full_name: str | None = None
    default_tone: str | None = None


class AdvisorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    default_tone: str
