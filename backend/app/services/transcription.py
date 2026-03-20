"""Local transcription service backed by faster-whisper.

The WhisperModel is lazily initialised on first use so that application
startup remains instant regardless of model weight size.

Usage::

    from app.services.transcription import transcription_service
    transcript = await transcription_service.transcribe("/tmp/audio.m4a")
"""

import asyncio
import logging

import structlog
from faster_whisper import WhisperModel

from app.core.config import settings

logger = structlog.get_logger(__name__)

_MODEL_SIZE = settings.WHISPER_MODEL


class TranscriptionError(Exception):
    """Raised when faster-whisper fails to transcribe audio."""

    def __init__(self, detail: str = "Transcription failed") -> None:
        self.detail = detail
        super().__init__(detail)


class TranscriptionService:
    """Lazy-loaded wrapper around faster-whisper's WhisperModel.

    The model weights (~145 MB for base.en) are downloaded from HuggingFace
    Hub on the first call and cached at ``~/.cache/huggingface/hub``.
    """

    def __init__(self) -> None:
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            logger.info("whisper_model_loading", model=_MODEL_SIZE)
            self._model = WhisperModel(
                _MODEL_SIZE,
                device="cpu",
                compute_type="int8",
            )
            logger.info("whisper_model_ready", model=_MODEL_SIZE)
        return self._model

    def _transcribe_sync(self, audio_path: str) -> str:
        """Blocking transcription — must be called inside asyncio.to_thread."""
        model = self._get_model()
        log = logger.bind(audio_path=audio_path)
        log.info("transcription_started")
        try:
            segments, _ = model.transcribe(audio_path, beam_size=5)
            transcript = " ".join(seg.text.strip() for seg in segments)
            log.info("transcription_complete", chars=len(transcript))
            return transcript
        except Exception as exc:
            log.error("transcription_failed", error=str(exc), exc_info=True)
            raise TranscriptionError(f"Transcription failed: {exc}") from exc

    async def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file and return the full transcript string.

        Runs the synchronous WhisperModel call in a thread pool so the
        FastAPI event loop is never blocked.

        Args:
            audio_path: Absolute path to the audio file on disk.

        Returns:
            The full transcript as a single string.

        Raises:
            TranscriptionError: If faster-whisper raises during transcription.
        """
        return await asyncio.to_thread(self._transcribe_sync, audio_path)


# Module-level singleton consumed by the audio router
transcription_service = TranscriptionService()
