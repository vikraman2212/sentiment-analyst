import uuid

from pydantic import BaseModel


class AudioUploadResponse(BaseModel):
    status: str
    extracted_tags_count: int
    interaction_id: uuid.UUID
