"""POST /api/v1/audio — audio ingestion endpoints.

Two-step upload pattern:
  1. ``POST /audio/presign`` — client requests a pre-signed PUT URL; audio never
     passes through this server.
  2. ``POST /audio/process`` — after the client has PUT the file directly to MinIO,
     the server downloads it, transcribes, and extracts context tags.
"""

import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dependencies.db import get_db
from app.repositories.client import ClientRepository
from app.repositories.interaction import InteractionRepository
from app.schemas.audio import AudioUploadResponse, PresignRequest, PresignResponse, ProcessRequest
from app.schemas.interaction import InteractionCreate
from app.services.extraction import ExtractionError, extraction_service
from app.services.storage import StorageError, storage_service
from app.services.transcription import TranscriptionError, transcription_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/audio", tags=["audio"])

_ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/wav",
    "audio/wave",
    "audio/webm",
    "audio/ogg",
}


@router.post(
    "/presign",
    response_model=PresignResponse,
    status_code=status.HTTP_200_OK,
)
async def request_presigned_url(
    payload: PresignRequest,
    db: AsyncSession = Depends(get_db),
) -> PresignResponse:
    """Return a pre-signed PUT URL so the client can upload audio directly to MinIO.

    Steps:
    1. Validate client exists.
    2. Validate content type is an accepted audio format.
    3. Generate a unique object key scoped to the client.
    4. Return the pre-signed URL and object key for the subsequent process call.
    """
    log = logger.bind(client_id=str(payload.client_id), filename=payload.filename)
    log.info("audio_presign_started")

    client = await ClientRepository(db).get_by_id(payload.client_id)
    if client is None:
        log.warning("audio_presign_client_not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {payload.client_id} not found",
        )

    if payload.content_type not in _ALLOWED_CONTENT_TYPES:
        log.warning("audio_presign_unsupported_type", content_type=payload.content_type)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type '{payload.content_type}'",
        )

    ext = Path(payload.filename).suffix or ".m4a"
    object_key = f"{payload.client_id}/{uuid.uuid4()}{ext}"

    try:
        upload_url = await storage_service.generate_presigned_put_url(object_key, payload.content_type)
    except StorageError as exc:
        log.error("audio_presign_storage_failed", error=exc.detail)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
        ) from exc

    log.info("audio_presign_complete", object_key=object_key)
    return PresignResponse(
        upload_url=upload_url,
        object_key=object_key,
        expires_in=settings.MINIO_PRESIGN_EXPIRY,
    )


@router.post(
    "/process",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def process_audio(
    payload: ProcessRequest,
    db: AsyncSession = Depends(get_db),
) -> AudioUploadResponse:
    """Download a previously uploaded audio file, transcribe it, and extract tags.

    Steps:
    1. Validate client exists.
    2. Download the object from MinIO to a temp file.
    3. Transcribe via faster-whisper (runs in thread pool).
    4. Persist ``Interaction`` row with transcript and object key.
    5. Extract context tags via Ollama (best-effort; failure is non-fatal).
    6. Return interaction id and extracted tag count.
    """
    log = logger.bind(client_id=str(payload.client_id), object_key=payload.object_key)
    log.info("audio_process_started")

    client = await ClientRepository(db).get_by_id(payload.client_id)
    if client is None:
        log.warning("audio_process_client_not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {payload.client_id} not found",
        )

    try:
        tmp_path = await storage_service.download_to_tempfile(payload.object_key)
    except StorageError as exc:
        log.error("audio_process_download_failed", error=exc.detail)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio object '{payload.object_key}' not found in storage",
        ) from exc

    try:
        transcript = await transcription_service.transcribe(tmp_path)
    except TranscriptionError as exc:
        log.error("audio_process_transcription_failed", error=exc.detail)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.detail,
        ) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    interaction = await InteractionRepository(db).create(
        InteractionCreate(
            client_id=payload.client_id,
            type="voice_memo",
            raw_transcript=transcript,
            audio_file_key=payload.object_key,
        )
    )
    log.info("audio_process_interaction_saved", interaction_id=str(interaction.id))

    extracted_tags_count = 0
    try:
        extracted_tags_count = await extraction_service.extract(
            transcript=transcript,
            client_id=payload.client_id,
            interaction_id=interaction.id,
            db=db,
        )
    except ExtractionError as exc:
        log.warning(
            "audio_process_extraction_degraded",
            error=exc.detail,
            interaction_id=str(interaction.id),
        )

    log.info(
        "audio_process_complete",
        interaction_id=str(interaction.id),
        extracted_tags=extracted_tags_count,
    )
    return AudioUploadResponse(
        status="success",
        extracted_tags_count=extracted_tags_count,
        interaction_id=interaction.id,
    )
