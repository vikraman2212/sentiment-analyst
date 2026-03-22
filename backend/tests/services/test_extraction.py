"""Unit tests for ExtractionService.

All external dependencies (LLMProvider, ClientContextRepository) are mocked so
no network or database is required. Tests follow AAA (Arrange → Act → Assert).
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ExtractionError
from app.core.llm_provider import LLMResult
from app.services.extraction import ExtractionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_INTERACTION_ID = uuid.uuid4()

_VALID_JSON = json.dumps(
    {
        "tags": [
            {"category": "personal_interest", "content": "Enjoys golf"},
            {"category": "financial_goal", "content": "Retire at 60"},
        ]
    }
)

_SINGLE_TAG_JSON = json.dumps(
    {"tags": [{"category": "family_event", "content": "Daughter starting college"}]}
)


def _make_result(response: str) -> LLMResult:
    """Build a fake LLMResult with the given response text."""
    return LLMResult(
        response=response,
        prompt="<prompt>",
        prompt_tokens=10,
        completion_tokens=20,
        latency_ms=100.0,
    )


def _make_provider(responses: list[str]) -> AsyncMock:
    """Return a mock LLMProvider whose complete() yields the given responses."""
    provider = AsyncMock()
    provider.complete = AsyncMock(
        side_effect=[_make_result(r) for r in responses]
    )
    return provider


def _make_service(provider: AsyncMock) -> ExtractionService:
    return ExtractionService(provider=provider)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_extraction_returns_correct_count() -> None:
    """LLM returns valid JSON → 2 tags persisted → count=2."""
    provider = _make_provider([_VALID_JSON])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch(
        "app.services.extraction.ClientContextRepository"
    ) as mock_repo_cls:
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
    """First LLM call returns garbage; second call returns valid JSON → count=1."""
    provider = _make_provider(["NOT JSON AT ALL", _SINGLE_TAG_JSON])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch(
        "app.services.extraction.ClientContextRepository"
    ) as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock()])
        mock_repo_cls.return_value = mock_repo

        count = await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    assert count == 1
    assert provider.complete.await_count == 2


@pytest.mark.asyncio
async def test_all_retries_exhausted_raises_extraction_error() -> None:
    """Both LLM calls return garbage JSON → ExtractionError raised."""
    provider = _make_provider(["JUNK OUTPUT {]", "STILL JUNK"])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch("app.services.extraction.ClientContextRepository"):
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
    provider = _make_provider([body])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch(
        "app.services.extraction.ClientContextRepository"
    ) as mock_repo_cls:
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
    """LLM returns valid JSON with empty tags array → count=0, no DB writes."""
    body = json.dumps({"tags": []})
    provider = _make_provider([body])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch(
        "app.services.extraction.ClientContextRepository"
    ) as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        count = await service.extract("No relevant content.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    assert count == 0
    mock_repo.bulk_create.assert_not_called()
