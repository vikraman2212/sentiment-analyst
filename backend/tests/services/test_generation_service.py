"""Unit tests for GenerationService.

All external dependencies (LLMProvider, ContextAssemblyService,
MessageDraftService) are mocked so no network or database is required.
Tests follow AAA (Arrange → Act → Assert).
"""

from collections.abc import Generator

import uuid
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app.services.generation_service as _generation_mod
from app.core.exceptions import GenerationError, LLMProviderError
from app.core.llm_provider import LLMResult
from app.schemas.context_assembly import AssembledContext, FinancialSummary
from app.services.generation_service import GenerationService, _normalize

from tests.services.conftest import get_metric_value, make_span_exporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_DRAFT_ID = uuid.uuid4()


def _make_assembled_context(prompt_block: str = "## Client Profile\nName: Jane Doe") -> AssembledContext:
    return AssembledContext(
        client_id=_CLIENT_ID,
        client_name="Jane Doe",
        financial_summary=FinancialSummary(
            total_aum=Decimal("1_200_000"),
            ytd_return_pct=Decimal("5.3"),
            risk_profile="moderate",
        ),
        context_tags=[],
        prompt_block=prompt_block,
    )


def _make_llm_result(response: str) -> LLMResult:
    return LLMResult(
        response=response,
        prompt="<prompt>",
        prompt_tokens=80,
        completion_tokens=40,
        latency_ms=250.0,
    )


def _make_draft(content: str) -> MagicMock:
    draft = MagicMock()
    draft.id = _DRAFT_ID
    draft.client_id = _CLIENT_ID
    draft.trigger_type = "review_due"
    draft.generated_content = content
    return draft


def _make_service(
    provider_response: str | None = None,
    provider_side_effect: Exception | None = None,
    assembled_context: AssembledContext | None = None,
    existing_pending_draft: MagicMock | None = None,
) -> tuple[GenerationService, AsyncMock, AsyncMock, AsyncMock]:
    """Build a GenerationService with all dependencies mocked.

    Returns:
        Tuple of (service, mock_provider, mock_context_svc, mock_draft_svc).
    """
    mock_provider = AsyncMock()
    if provider_side_effect is not None:
        mock_provider.complete = AsyncMock(side_effect=provider_side_effect)
    else:
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_result(provider_response or "Clean email body text.")
        )

    mock_context_svc = AsyncMock()
    mock_context_svc.assemble = AsyncMock(
        return_value=assembled_context or _make_assembled_context()
    )

    mock_draft_svc = AsyncMock()
    mock_draft_svc.create = AsyncMock(
        return_value=_make_draft(provider_response or "Clean email body text.")
    )
    mock_draft_svc.find_pending_by_client = AsyncMock(return_value=existing_pending_draft)
    mock_draft_svc.delete = AsyncMock(return_value=None)

    service = GenerationService.__new__(GenerationService)
    service._provider = mock_provider
    service._context_svc = mock_context_svc
    service._draft_svc = mock_draft_svc

    return service, mock_provider, mock_context_svc, mock_draft_svc


@pytest.fixture(autouse=True)
def patch_background_audit_tasks() -> Generator[None, None, None]:
    """Patch fire-and-forget audit task scheduling to keep tests deterministic."""
    def _discard_task(coro: object) -> MagicMock:
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        return MagicMock()

    with patch(
        "app.services.generation_service.asyncio.create_task",
        side_effect=_discard_task,
    ):
        yield


# ---------------------------------------------------------------------------
# GenerationService tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_happy_path() -> None:
    """Full pipeline: context assembled, LLM called, draft persisted, draft returned."""
    email_body = "Hi Jane, just a quick note about your portfolio."
    service, mock_provider, mock_context_svc, mock_draft_svc = _make_service(
        provider_response=email_body
    )

    draft = await service.generate(_CLIENT_ID, "review_due")

    assert draft.id == _DRAFT_ID
    mock_context_svc.assemble.assert_awaited_once_with(_CLIENT_ID)
    mock_provider.complete.assert_awaited_once()
    call_kwargs = mock_provider.complete.call_args
    assert call_kwargs.kwargs["model"] is not None
    assert call_kwargs.kwargs["system"] is not None
    mock_draft_svc.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_client_not_found_propagates() -> None:
    """NotFoundError from ContextAssemblyService propagates unchanged."""
    from app.core.exceptions import NotFoundError

    service, _, mock_context_svc, _ = _make_service()
    mock_context_svc.assemble = AsyncMock(
        side_effect=NotFoundError(f"Client {_CLIENT_ID} not found")
    )

    with pytest.raises(NotFoundError):
        await service.generate(_CLIENT_ID, "review_due")


@pytest.mark.asyncio
async def test_generate_llm_provider_error_raises_generation_error() -> None:
    """LLMProviderError from provider.complete → GenerationError raised."""
    service, _, _, _ = _make_service(
        provider_side_effect=LLMProviderError("Connection refused")
    )

    with pytest.raises(GenerationError, match="LLM provider failed"):
        await service.generate(_CLIENT_ID, "review_due")


@pytest.mark.asyncio
async def test_generate_passes_prompt_block_to_provider() -> None:
    """The assembled prompt_block is forwarded verbatim as the LLM prompt."""
    custom_block = "## Client Profile\nName: Bob Smith\n## Financial Summary\nAUM: $500k"
    service, mock_provider, _, _ = _make_service(
        assembled_context=_make_assembled_context(prompt_block=custom_block)
    )

    await service.generate(_CLIENT_ID, "review_due")

    prompt_arg = mock_provider.complete.call_args[0][0]
    assert prompt_arg == custom_block


# ---------------------------------------------------------------------------
# _normalize tests
# ---------------------------------------------------------------------------


def test_normalize_strips_subject_line() -> None:
    raw = "Subject: Your Portfolio Update\nHi Jane, here is your update."
    assert _normalize(raw) == "Hi Jane, here is your update."


def test_normalize_strips_salutation() -> None:
    raw = "Dear Jane,\nHi Jane, here is your update."
    result = _normalize(raw)
    assert "Dear Jane" not in result
    assert "here is your update" in result


def test_normalize_strips_sign_off() -> None:
    raw = "Hi Jane, great news!\nWarm regards,\nYour Advisor"
    result = _normalize(raw)
    assert "Warm regards" not in result
    assert "Hi Jane, great news!" in result


def test_normalize_clean_input_unchanged() -> None:
    raw = "Hi Jane, your portfolio is performing well this quarter."
    assert _normalize(raw) == raw


def test_normalize_trims_whitespace() -> None:
    raw = "\n\n  Hi Jane.  \n\n"
    assert _normalize(raw) == "Hi Jane."


# ---------------------------------------------------------------------------
# Idempotency guard tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_existing_pending_draft() -> None:
    """When a pending draft exists and force=False, return it without calling the LLM."""
    existing = _make_draft("Existing email body.")
    service, mock_provider, mock_context_svc, mock_draft_svc = _make_service(
        existing_pending_draft=existing
    )

    result = await service.generate(_CLIENT_ID, "review_due")

    assert result is existing
    mock_draft_svc.find_pending_by_client.assert_awaited_once_with(_CLIENT_ID)
    mock_provider.complete.assert_not_awaited()
    mock_context_svc.assemble.assert_not_awaited()
    mock_draft_svc.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_force_deletes_existing_and_regenerates() -> None:
    """When force=True and a pending draft exists, delete it then run the full pipeline."""
    existing = _make_draft("Old email body.")
    new_body = "Fresh regenerated email."
    service, mock_provider, mock_context_svc, mock_draft_svc = _make_service(
        provider_response=new_body,
        existing_pending_draft=existing,
    )

    result = await service.generate(_CLIENT_ID, "review_due", force=True)

    mock_draft_svc.find_pending_by_client.assert_awaited_once_with(_CLIENT_ID)
    mock_draft_svc.delete.assert_awaited_once_with(existing.id)
    mock_context_svc.assemble.assert_awaited_once_with(_CLIENT_ID)
    mock_provider.complete.assert_awaited_once()
    mock_draft_svc.create.assert_awaited_once()
    assert result.id == _DRAFT_ID


@pytest.mark.asyncio
async def test_generate_no_pending_proceeds_normally() -> None:
    """When no pending draft exists, the full pipeline runs without calling delete."""
    service, mock_provider, mock_context_svc, mock_draft_svc = _make_service()

    result = await service.generate(_CLIENT_ID, "review_due")

    mock_draft_svc.find_pending_by_client.assert_awaited_once_with(_CLIENT_ID)
    mock_draft_svc.delete.assert_not_awaited()
    mock_context_svc.assemble.assert_awaited_once_with(_CLIENT_ID)
    mock_provider.complete.assert_awaited_once()
    mock_draft_svc.create.assert_awaited_once()
    assert result.id == _DRAFT_ID


@pytest.mark.asyncio
async def test_generate_create_payload_has_correct_fields() -> None:
    """MessageDraftCreate passed to create() contains the correct client_id and trigger_type."""
    from app.schemas.message_draft import MessageDraftCreate

    service, _, _, mock_draft_svc = _make_service()

    await service.generate(_CLIENT_ID, "review_due")

    call_args = mock_draft_svc.create.call_args[0][0]
    assert isinstance(call_args, MessageDraftCreate)
    assert call_args.client_id == _CLIENT_ID
    assert call_args.trigger_type == "review_due"


@pytest.mark.asyncio
async def test_generate_records_success_metrics() -> None:
    """Successful generation updates request and duration metrics."""
    service, _, _, _ = _make_service(provider_response="Email body.")
    before_requests = get_metric_value(
        "sentiment_generation_requests_total",
        {"status": "success"},
    )
    before_duration = get_metric_value(
        "sentiment_generation_duration_seconds_count",
        {"status": "success"},
    )

    await service.generate(_CLIENT_ID, "review_due")

    assert get_metric_value(
        "sentiment_generation_requests_total",
        {"status": "success"},
    ) == before_requests + 1
    assert get_metric_value(
        "sentiment_generation_duration_seconds_count",
        {"status": "success"},
    ) == before_duration + 1


@pytest.mark.asyncio
async def test_generate_records_cached_metrics() -> None:
    """Returning an existing draft records the cached generation status."""
    existing = _make_draft("Existing email body.")
    service, _, _, _ = _make_service(existing_pending_draft=existing)
    before_requests = get_metric_value(
        "sentiment_generation_requests_total",
        {"status": "cached"},
    )

    await service.generate(_CLIENT_ID, "review_due")

    assert get_metric_value(
        "sentiment_generation_requests_total",
        {"status": "cached"},
    ) == before_requests + 1


@pytest.mark.asyncio
async def test_generate_records_error_metrics() -> None:
    """LLM failures update error request and duration metrics."""
    service, _, _, _ = _make_service(
        provider_side_effect=LLMProviderError("Connection refused")
    )
    before_requests = get_metric_value(
        "sentiment_generation_requests_total",
        {"status": "error"},
    )
    before_duration = get_metric_value(
        "sentiment_generation_duration_seconds_count",
        {"status": "error"},
    )

    with pytest.raises(GenerationError, match="LLM provider failed"):
        await service.generate(_CLIENT_ID, "review_due")

    assert get_metric_value(
        "sentiment_generation_requests_total",
        {"status": "error"},
    ) == before_requests + 1
    assert get_metric_value(
        "sentiment_generation_duration_seconds_count",
        {"status": "error"},
    ) == before_duration + 1


# ---------------------------------------------------------------------------
# Span tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Fixture: wire a fresh in-memory exporter into the generation service tracer."""
    exporter, provider = make_span_exporter()
    original = _generation_mod._tracer
    _generation_mod._tracer = provider.get_tracer(__name__)
    yield exporter
    _generation_mod._tracer = original


@pytest.mark.asyncio
async def test_generate_emits_pipeline_span(span_exporter: InMemorySpanExporter) -> None:
    """Happy path: a ``generation.pipeline`` span is recorded with client and trigger attrs."""
    service, _, _, _ = _make_service(provider_response="Email body.")

    await service.generate(_CLIENT_ID, "review_due")

    spans = span_exporter.get_finished_spans()
    pipeline_spans = [s for s in spans if s.name == "generation.pipeline"]
    assert len(pipeline_spans) == 1
    span = pipeline_spans[0]
    attributes = cast(dict[str, object], span.attributes or {})
    assert attributes["client_id"] == str(_CLIENT_ID)
    assert attributes["trigger_type"] == "review_due"
    assert "draft_id" in attributes


@pytest.mark.asyncio
async def test_generate_emits_persist_span(span_exporter: InMemorySpanExporter) -> None:
    """Happy path: a ``generation.persist`` child span is emitted with draft_id attribute."""
    service, _, _, _ = _make_service(provider_response="Email body.")

    await service.generate(_CLIENT_ID, "review_due")

    spans = span_exporter.get_finished_spans()
    persist_spans = [s for s in spans if s.name == "generation.persist"]
    assert len(persist_spans) == 1
    attributes = cast(dict[str, object], persist_spans[0].attributes or {})
    assert attributes["draft_id"] == str(_DRAFT_ID)


@pytest.mark.asyncio
async def test_generate_pipeline_span_error_on_llm_failure(
    span_exporter: InMemorySpanExporter,
) -> None:
    """LLMProviderError → pipeline span status is ERROR with exception recorded."""
    from opentelemetry.trace import StatusCode

    service, _, _, _ = _make_service(
        provider_side_effect=LLMProviderError("Connection refused")
    )

    with pytest.raises(GenerationError):
        await service.generate(_CLIENT_ID, "review_due")

    spans = span_exporter.get_finished_spans()
    pipeline_spans = [s for s in spans if s.name == "generation.pipeline"]
    assert len(pipeline_spans) == 1
    assert pipeline_spans[0].status.status_code == StatusCode.ERROR
    assert any(e.name == "exception" for e in pipeline_spans[0].events)

