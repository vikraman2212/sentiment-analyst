"""POST /api/v1/audio/upload — audio ingestion endpoint.

Accepts a multipart upload containing a client_id and an audio file,
transcribes locally via faster-whisper, persists the interaction, and
returns a structured response for the Flutter client.
"""

import tempfile
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.repositories.client import ClientRepository
from app.repositories.interaction import InteractionRepository
from app.schemas.audio import AudioUploadResponse
from app.schemas.interaction import InteractionCreate
from app.services.extraction import ExtractionError, extraction_service
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
    "/upload",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_audio(
    client_id: uuid.UUID = Form(..., description="ID of the client being discussed"),
    audio_file: UploadFile = File(..., description="Audio recording (.m4a, .wav, etc.)"),
    db: AsyncSession = Depends(get_db),
) -> AudioUploadResponse:
    """Receive an audio memo, transcribe it locally, and persist the interaction.

    Steps:
    1. Validate client exists.
    2. Save audio to a temp file.
    3. Transcribe via faster-whisper (runs in thread pool).
    4. Persist ``Interaction`` row with transcript.
    5. Return interaction id and placeholder tag count for the extraction pipeline.
    """
    log = logger.bind(client_id=str(client_id), filename=audio_file.filename)
    log.info("audio_upload_started")

    # 1 — Verify client exists
    client = await ClientRepository(db).get_by_id(client_id)
    if client is None:
        log.warning("audio_upload_client_not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )

    # 2 — Write audio to temp file
    suffix = Path(audio_file.filename or "audio").suffix or ".m4a"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        content = await audio_file.read()
        tmp.write(content)
    log.info("audio_upload_saved", tmp_path=tmp_path, bytes=len(content))

    # 3 — Transcribe locally
    try:
        transcript = await transcription_service.transcribe(tmp_path)
    except TranscriptionError as exc:
        log.error("audio_upload_transcription_failed", error=exc.detail)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.detail,
        ) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # 4 — Persist interaction
    interaction = await InteractionRepository(db).create(
        InteractionCreate(
            client_id=client_id,
            type="voice_memo",
            raw_transcript=transcript,
        )
    )
    log.info("audio_upload_interaction_saved", interaction_id=str(interaction.id))

    # 5 — Extract context tags via Ollama (best-effort; failure is non-fatal)
    extracted_tags_count = 0
    try:
        extracted_tags_count = await extraction_service.extract(
            transcript=transcript,
            client_id=client_id,
            interaction_id=interaction.id,
            db=db,
        )
    except ExtractionError as exc:
        log.warning(
            "audio_upload_extraction_degraded",
            error=exc.detail,
            interaction_id=str(interaction.id),
        )

    log.info(
        "audio_upload_complete",
        interaction_id=str(interaction.id),
        extracted_tags=extracted_tags_count,
    )
    return AudioUploadResponse(
        status="success",
        extracted_tags_count=extracted_tags_count,
        interaction_id=interaction.id,
    )
