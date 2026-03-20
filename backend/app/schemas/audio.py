import uuid

from pydantic import BaseModel


class PresignRequest(BaseModel):
    client_id: uuid.UUID
    filename: str
    content_type: str


class PresignResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class ProcessRequest(BaseModel):
    client_id: uuid.UUID
    object_key: str


class AudioUploadResponse(BaseModel):
    status: str
    extracted_tags_count: int
    interaction_id: uuid.UUID
