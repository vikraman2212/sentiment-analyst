import uuid

from pydantic import BaseModel, ConfigDict, Field


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


# --- MinIO webhook event payload ---

class MinioS3Object(BaseModel):
    """S3 object info from a MinIO event notification record."""

    key: str  # URL-encoded object key
    size: int = 0
    contentType: str = ""


class MinioS3Bucket(BaseModel):
    """S3 bucket info from a MinIO event notification record."""

    name: str


class MinioS3Info(BaseModel):
    """S3 section of a MinIO event notification record."""

    model_config = ConfigDict(populate_by_name=True)

    bucket: MinioS3Bucket
    object_: MinioS3Object = Field(alias="object")


class MinioRecord(BaseModel):
    """Single record in a MinIO event notification payload."""

    eventName: str
    s3: MinioS3Info


class MinioWebhookPayload(BaseModel):
    """MinIO event notification webhook body (S3-compatible format)."""

    Records: list[MinioRecord] = []
