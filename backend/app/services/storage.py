"""MinIO / S3-compatible blob storage service.

Wraps aioboto3 to provide pre-signed PUT URLs for direct client uploads and
helpers for server-side download and deletion used by the transcription pipeline.
"""

import tempfile
from pathlib import Path

import aioboto3  # type: ignore[import-untyped]
import structlog
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from app.core.config import settings

logger = structlog.get_logger(__name__)


class StorageError(Exception):
    """Raised when a storage operation fails."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class StorageService:
    """Async wrapper around aioboto3 for MinIO / AWS S3 operations."""

    def __init__(self) -> None:
        self._session = aioboto3.Session(
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1",  # MinIO ignores region; boto3 requires a value
        )
        self._bucket = settings.MINIO_BUCKET
        self._endpoint = settings.MINIO_ENDPOINT

    async def ensure_bucket_exists(self) -> None:
        """Create the configured bucket if it does not already exist."""
        log = logger.bind(bucket=self._bucket)
        log.info("storage_ensure_bucket_started")
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                try:
                    await s3.head_bucket(Bucket=self._bucket)
                    log.info("storage_bucket_exists")
                except ClientError as exc:
                    code = exc.response["Error"]["Code"]
                    if code in ("404", "NoSuchBucket"):
                        await s3.create_bucket(Bucket=self._bucket)
                        log.info("storage_bucket_created")
                    else:
                        raise
        except ClientError as exc:
            log.error("storage_ensure_bucket_failed", error=str(exc))
            raise StorageError(f"Could not ensure bucket exists: {exc}") from exc

    async def generate_presigned_put_url(self, object_key: str, content_type: str) -> str:
        """Return a pre-signed PUT URL valid for ``settings.MINIO_PRESIGN_EXPIRY`` seconds.

        Args:
            object_key: The S3 object key (path within the bucket).
            content_type: MIME type the client must supply in the PUT request.

        Returns:
            A pre-signed URL string the Flutter client can PUT the audio file to directly.
        """
        log = logger.bind(object_key=object_key, content_type=content_type)
        log.info("storage_presign_started")
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                url: str = await s3.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self._bucket,
                        "Key": object_key,
                        "ContentType": content_type,
                    },
                    ExpiresIn=settings.MINIO_PRESIGN_EXPIRY,
                )
            log.info("storage_presign_complete")
            return url
        except ClientError as exc:
            log.error("storage_presign_failed", error=str(exc))
            raise StorageError(f"Could not generate pre-signed URL: {exc}") from exc

    async def download_to_tempfile(self, object_key: str) -> str:
        """Download an S3 object to a local temporary file.

        Args:
            object_key: The S3 object key to download.

        Returns:
            Absolute path to the temporary file. Caller is responsible for deletion.
        """
        log = logger.bind(object_key=object_key, bucket=self._bucket)
        log.info("storage_download_started")
        suffix = Path(object_key).suffix or ".m4a"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                await s3.download_file(self._bucket, object_key, tmp_path)
            log.info("storage_download_complete", tmp_path=tmp_path)
            return tmp_path
        except ClientError as exc:
            Path(tmp_path).unlink(missing_ok=True)
            log.error("storage_download_failed", error=str(exc))
            raise StorageError(f"Could not download object '{object_key}': {exc}") from exc

    async def delete_object(self, object_key: str) -> None:
        """Delete an object from the bucket.

        Args:
            object_key: The S3 object key to delete.
        """
        log = logger.bind(object_key=object_key, bucket=self._bucket)
        log.info("storage_delete_started")
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                await s3.delete_object(Bucket=self._bucket, Key=object_key)
            log.info("storage_delete_complete")
        except ClientError as exc:
            log.error("storage_delete_failed", error=str(exc))
            raise StorageError(f"Could not delete object '{object_key}': {exc}") from exc


storage_service = StorageService()
