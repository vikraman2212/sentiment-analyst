"""Unit tests for ExtractionService.

All external dependencies (LLMProvider, ClientContextRepository) are mocked so
no network or database is required. Tests follow AAA (Arrange → Act → Assert).
"""

from collections.abc import Generator

import json
import uuid
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app.services.extraction as _extraction_mod
from app.core.exceptions import ExtractionError
from app.core.llm_provider import LLMResult
from app.services.extraction import ExtractionService

from tests.services.conftest import get_metric_value, make_span_exporter


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


@pytest.mark.asyncio
async def test_extract_records_success_metrics() -> None:
    """Successful extraction updates request, duration, and saved-tag metrics."""
    provider = _make_provider([_VALID_JSON])
    service = _make_service(provider)
    mock_db = AsyncMock()
    before_requests = get_metric_value(
        "sentiment_extraction_requests_total",
        {"status": "success"},
    )
    before_duration = get_metric_value(
        "sentiment_extraction_duration_seconds_count",
        {"status": "success"},
    )
    before_saved = get_metric_value("sentiment_extraction_tags_saved_total")

    with patch("app.services.extraction.ClientContextRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock(), MagicMock()])
        mock_repo_cls.return_value = mock_repo

        await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    assert get_metric_value(
        "sentiment_extraction_requests_total",
        {"status": "success"},
    ) == before_requests + 1
    assert get_metric_value(
        "sentiment_extraction_duration_seconds_count",
        {"status": "success"},
    ) == before_duration + 1
    assert get_metric_value("sentiment_extraction_tags_saved_total") == before_saved + 2


@pytest.mark.asyncio
async def test_extract_records_error_metrics() -> None:
    """Failed extraction updates error request and duration metrics."""
    provider = _make_provider(["JUNK OUTPUT {]", "STILL JUNK"])
    service = _make_service(provider)
    mock_db = AsyncMock()
    before_requests = get_metric_value(
        "sentiment_extraction_requests_total",
        {"status": "error"},
    )
    before_duration = get_metric_value(
        "sentiment_extraction_duration_seconds_count",
        {"status": "error"},
    )

    with patch("app.services.extraction.ClientContextRepository"):
        with pytest.raises(ExtractionError):
            await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    assert get_metric_value(
        "sentiment_extraction_requests_total",
        {"status": "error"},
    ) == before_requests + 1
    assert get_metric_value(
        "sentiment_extraction_duration_seconds_count",
        {"status": "error"},
    ) == before_duration + 1


# ---------------------------------------------------------------------------
# Span tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Fixture: wire a fresh in-memory exporter into the extraction service tracer."""
    exporter, provider = make_span_exporter()
    original = _extraction_mod._tracer
    _extraction_mod._tracer = provider.get_tracer(__name__)
    yield exporter
    _extraction_mod._tracer = original


@pytest.mark.asyncio
async def test_extract_emits_pipeline_span(span_exporter: InMemorySpanExporter) -> None:
    """Happy path: an ``extraction.pipeline`` span is recorded with client and interaction attrs."""
    provider = _make_provider([_VALID_JSON])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch("app.services.extraction.ClientContextRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock(), MagicMock()])
        mock_repo_cls.return_value = mock_repo

        await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    spans = span_exporter.get_finished_spans()
    pipeline_spans = [s for s in spans if s.name == "extraction.pipeline"]
    assert len(pipeline_spans) == 1
    span = pipeline_spans[0]
    attributes = cast(dict[str, object], span.attributes or {})
    assert attributes["client_id"] == str(_CLIENT_ID)
    assert attributes["interaction_id"] == str(_INTERACTION_ID)
    assert attributes["tags_saved"] == 2


@pytest.mark.asyncio
async def test_extract_emits_llm_attempt_span(span_exporter: InMemorySpanExporter) -> None:
    """Happy path: one ``extraction.llm_attempt`` span is emitted for the first attempt."""
    provider = _make_provider([_VALID_JSON])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch("app.services.extraction.ClientContextRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock()])
        mock_repo_cls.return_value = mock_repo

        await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    spans = span_exporter.get_finished_spans()
    attempt_spans = [s for s in spans if s.name == "extraction.llm_attempt"]
    assert len(attempt_spans) == 1
    attributes = cast(dict[str, object], attempt_spans[0].attributes or {})
    assert attributes["attempt"] == 1
    assert attributes["parse_success"] is True


@pytest.mark.asyncio
async def test_extract_retry_emits_two_attempt_spans(span_exporter: InMemorySpanExporter) -> None:
    """Retry path: two ``extraction.llm_attempt`` spans emitted, retry event on pipeline span."""
    provider = _make_provider(["NOT JSON", _SINGLE_TAG_JSON])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch("app.services.extraction.ClientContextRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock()])
        mock_repo_cls.return_value = mock_repo

        await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    spans = span_exporter.get_finished_spans()
    attempt_spans = [s for s in spans if s.name == "extraction.llm_attempt"]
    assert len(attempt_spans) == 2
    first_attributes = cast(dict[str, object], attempt_spans[0].attributes or {})
    second_attributes = cast(dict[str, object], attempt_spans[1].attributes or {})
    assert first_attributes["attempt"] == 1
    assert first_attributes["parse_success"] is False
    assert second_attributes["attempt"] == 2
    assert second_attributes["parse_success"] is True

    pipeline_spans = [s for s in spans if s.name == "extraction.pipeline"]
    assert len(pipeline_spans) == 1
    event_names = [e.name for e in pipeline_spans[0].events]
    assert "extraction.retry" in event_names


@pytest.mark.asyncio
async def test_extract_emits_persist_span(span_exporter: InMemorySpanExporter) -> None:
    """Happy path: an ``extraction.persist`` child span is emitted with tags_saved attribute."""
    provider = _make_provider([_VALID_JSON])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch("app.services.extraction.ClientContextRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(return_value=[MagicMock(), MagicMock()])
        mock_repo_cls.return_value = mock_repo

        await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    spans = span_exporter.get_finished_spans()
    persist_spans = [s for s in spans if s.name == "extraction.persist"]
    assert len(persist_spans) == 1
    attributes = cast(dict[str, object], persist_spans[0].attributes or {})
    assert attributes["tags_saved"] == 2


@pytest.mark.asyncio
async def test_extract_pipeline_span_error_on_all_retries_failed(
    span_exporter: InMemorySpanExporter,
) -> None:
    """All attempts fail → pipeline span status is ERROR."""
    from opentelemetry.trace import StatusCode

    provider = _make_provider(["JUNK", "STILL JUNK"])
    service = _make_service(provider)
    mock_db = AsyncMock()

    with patch("app.services.extraction.ClientContextRepository"):
        with pytest.raises(ExtractionError):
            await service.extract("Transcript.", _CLIENT_ID, _INTERACTION_ID, mock_db)

    spans = span_exporter.get_finished_spans()
    pipeline_spans = [s for s in spans if s.name == "extraction.pipeline"]
    assert len(pipeline_spans) == 1
    assert pipeline_spans[0].status.status_code == StatusCode.ERROR

