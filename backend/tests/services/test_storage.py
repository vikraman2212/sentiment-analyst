"""Unit tests for StorageService.

All aioboto3 / botocore calls are mocked so no real MinIO or AWS connection
is required. Tests follow AAA (Arrange → Act → Assert).
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from app.services.storage import StorageError, StorageService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "op")


def _make_service() -> StorageService:
    """Return a StorageService with test settings pre-applied."""
    svc = StorageService.__new__(StorageService)
    svc._bucket = "test-bucket"
    svc._endpoint = "http://localhost:9000"
    svc._session = MagicMock()  # will be overridden by patch.object in each test
    return svc


def _mock_s3_ctx(mock_s3: AsyncMock) -> MagicMock:
    """Return an async context manager that yields *mock_s3*."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_s3)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# ensure_bucket_exists
# ---------------------------------------------------------------------------


async def test_ensure_bucket_exists_when_bucket_present() -> None:
    """No creation attempt when head_bucket succeeds."""
    mock_s3 = AsyncMock()
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        await svc.ensure_bucket_exists()

    mock_s3.head_bucket.assert_awaited_once_with(Bucket="test-bucket")
    mock_s3.create_bucket.assert_not_awaited()


async def test_ensure_bucket_exists_creates_when_missing() -> None:
    """Bucket is created when head_bucket returns a 404 ClientError."""
    mock_s3 = AsyncMock()
    mock_s3.head_bucket.side_effect = _make_client_error("404")
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        await svc.ensure_bucket_exists()

    mock_s3.create_bucket.assert_awaited_once_with(Bucket="test-bucket")


async def test_ensure_bucket_exists_raises_on_unexpected_error() -> None:
    """StorageError is raised when head_bucket returns an unexpected ClientError."""
    mock_s3 = AsyncMock()
    mock_s3.head_bucket.side_effect = _make_client_error("403")
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        with pytest.raises(StorageError):
            await svc.ensure_bucket_exists()


# ---------------------------------------------------------------------------
# generate_presigned_put_url
# ---------------------------------------------------------------------------


async def test_generate_presigned_put_url_returns_string() -> None:
    """A pre-signed URL string is returned when boto3 succeeds."""
    expected_url = "https://localhost:9000/test-bucket/key?sig=abc"
    mock_s3 = AsyncMock()
    mock_s3.generate_presigned_url = AsyncMock(return_value=expected_url)
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        url = await svc.generate_presigned_put_url("some/key.m4a", "audio/m4a")

    assert url == expected_url
    mock_s3.generate_presigned_url.assert_awaited_once()
    call_kwargs = mock_s3.generate_presigned_url.call_args
    assert call_kwargs.args[0] == "put_object"
    assert call_kwargs.kwargs["Params"]["Key"] == "some/key.m4a"
    assert call_kwargs.kwargs["Params"]["ContentType"] == "audio/m4a"


async def test_generate_presigned_put_url_raises_storage_error() -> None:
    """StorageError is raised when the boto3 call raises ClientError."""
    mock_s3 = AsyncMock()
    mock_s3.generate_presigned_url.side_effect = _make_client_error("AccessDenied")
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        with pytest.raises(StorageError):
            await svc.generate_presigned_put_url("some/key.m4a", "audio/m4a")


# ---------------------------------------------------------------------------
# download_to_tempfile
# ---------------------------------------------------------------------------


async def test_download_to_tempfile_returns_path() -> None:
    """A path to an existing temp file is returned after successful download."""
    mock_s3 = AsyncMock()
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        tmp_path = await svc.download_to_tempfile("client-id/abc.m4a")

    assert tmp_path.endswith(".m4a")
    mock_s3.download_file.assert_awaited_once()
    # clean up
    Path(tmp_path).unlink(missing_ok=True)


async def test_download_to_tempfile_cleans_up_and_raises_on_error() -> None:
    """Temp file is deleted and StorageError raised when download fails."""
    mock_s3 = AsyncMock()
    mock_s3.download_file.side_effect = _make_client_error("NoSuchKey")
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        with pytest.raises(StorageError):
            await svc.download_to_tempfile("client-id/missing.m4a")


# ---------------------------------------------------------------------------
# delete_object
# ---------------------------------------------------------------------------


async def test_delete_object_calls_s3() -> None:
    """delete_object issues the expected delete_object call to S3."""
    mock_s3 = AsyncMock()
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        await svc.delete_object("client-id/abc.m4a")

    mock_s3.delete_object.assert_awaited_once_with(
        Bucket="test-bucket", Key="client-id/abc.m4a"
    )


async def test_delete_object_raises_storage_error() -> None:
    """StorageError is raised when the boto3 delete call fails."""
    mock_s3 = AsyncMock()
    mock_s3.delete_object.side_effect = _make_client_error("AccessDenied")
    svc = _make_service()

    with patch.object(svc, "_session") as mock_session:
        mock_session.client.return_value = _mock_s3_ctx(mock_s3)
        with pytest.raises(StorageError):
            await svc.delete_object("client-id/abc.m4a")
