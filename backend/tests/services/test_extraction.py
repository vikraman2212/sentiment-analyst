"""Unit tests for ExtractionService.

All external dependencies (httpx, ClientContextRepository) are mocked so no
network or database is required. Tests follow AAA (Arrange → Act → Assert).
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ExtractionError
from app.services.extraction import ExtractionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_INTERACTION_ID = uuid.uuid4()

_VALID_OLLAMA_BODY = json.dumps(
    {
        "tags": [
            {"category": "personal_interest", "content": "Enjoys golf"},
            {"category": "financial_goal", "content": "Retire at 60"},
        ]
    }
)

_SINGLE_TAG_BODY = json.dumps(
    {"tags": [{"category": "family_event", "content": "Daughter starting college"}]}
)


def _make_httpx_response(body: str) -> MagicMock:
    """Return a mock httpx.Response that yields the given JSON body."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": body}
    return mock_resp


def _make_service() -> ExtractionService:
    return ExtractionService()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_extraction_returns_correct_count() -> None:
    """Happy path: Ollama returns valid JSON → 2 tags persisted → count=2."""
    service = _make_service()
    mock_db = AsyncMock()

    with (
        patch(
            "app.services.extraction.httpx.AsyncClient",
        ) as mock_client_cls,
        patch(
            "app.services.extraction.ClientContextRepository"
        ) as mock_repo_cls,
    ):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(_VALID_OLLAMA_BODY))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock(), MagicMock()])
        mock_repo_cls.return_value = mock_repo

        count = await service.extract("Some transcript text.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    assert count == 2
    mock_repo.bulk_create.assert_awaited_once()
    payloads = mock_repo.bulk_create.call_args[0][0]
    assert len(payloads) == 2


@pytest.mark.asyncio
async def test_retry_on_bad_json_succeeds() -> None:
    """First Ollama call returns garbage; second call returns valid JSON → count=1."""
    service = _make_service()
    mock_db = AsyncMock()

    bad_response = _make_httpx_response("NOT JSON AT ALL")
    good_response = _make_httpx_response(_SINGLE_TAG_BODY)

    with (
        patch("app.services.extraction.httpx.AsyncClient") as mock_client_cls,
        patch("app.services.extraction.ClientContextRepository") as mock_repo_cls,
    ):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=[bad_response, good_response])
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock()])
        mock_repo_cls.return_value = mock_repo

        count = await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    assert count == 1


@pytest.mark.asyncio
async def test_all_retries_exhausted_raises_extraction_error() -> None:
    """Both Ollama calls return garbage JSON → ExtractionError raised."""
    service = _make_service()
    mock_db = AsyncMock()

    bad_response = _make_httpx_response("JUNK OUTPUT {]")

    with (
        patch("app.services.extraction.httpx.AsyncClient") as mock_client_cls,
        patch("app.services.extraction.ClientContextRepository"),
    ):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=[bad_response, bad_response])
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ExtractionError):
            await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)


@pytest.mark.asyncio
async def test_invalid_category_tags_are_skipped() -> None:
    """Valid JSON but one tag has an unknown category → only valid tags persisted."""
    body = json.dumps(
        {
            "tags": [
                {"category": "personal_interest", "content": "Loves hiking"},
                {"category": "unknown_gibberish", "content": "Should be dropped"},
            ]
        }
    )
    service = _make_service()
    mock_db = AsyncMock()

    with (
        patch("app.services.extraction.httpx.AsyncClient") as mock_client_cls,
        patch("app.services.extraction.ClientContextRepository") as mock_repo_cls,
    ):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(body))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock()])
        mock_repo_cls.return_value = mock_repo

        count = await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    assert count == 1
    payloads = mock_repo.bulk_create.call_args[0][0]
    assert len(payloads) == 1
    assert payloads[0].category == "personal_interest"


@pytest.mark.asyncio
async def test_empty_tags_array_returns_zero() -> None:
    """Ollama returns valid JSON with empty tags array → count=0, no DB writes."""
    body = json.dumps({"tags": []})
    service = _make_service()
    mock_db = AsyncMock()

    with (
        patch("app.services.extraction.httpx.AsyncClient") as mock_client_cls,
        patch("app.services.extraction.ClientContextRepository") as mock_repo_cls,
    ):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response(body))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        count = await service.extract("No relevant content.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    assert count == 0
    mock_repo.bulk_create.assert_not_called()
