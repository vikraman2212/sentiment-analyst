"""Unit tests for GenerationService.

All external dependencies (LLMProvider, ContextAssemblyService,
MessageDraftService) are mocked so no network or database is required.
Tests follow AAA (Arrange → Act → Assert).
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import GenerationError, LLMProviderError
from app.core.llm_provider import LLMResult
from app.schemas.context_assembly import AssembledContext, FinancialSummary
from app.services.generation_service import GenerationService, _normalize


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

    with patch("app.services.generation_service.asyncio.create_task"):
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

    with patch("app.services.generation_service.asyncio.create_task"):
        with pytest.raises(GenerationError, match="LLM provider failed"):
            await service.generate(_CLIENT_ID, "review_due")


@pytest.mark.asyncio
async def test_generate_passes_prompt_block_to_provider() -> None:
    """The assembled prompt_block is forwarded verbatim as the LLM prompt."""
    custom_block = "## Client Profile\nName: Bob Smith\n## Financial Summary\nAUM: $500k"
    service, mock_provider, _, _ = _make_service(
        assembled_context=_make_assembled_context(prompt_block=custom_block)
    )

    with patch("app.services.generation_service.asyncio.create_task"):
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

    with patch("app.services.generation_service.asyncio.create_task"):
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

    with patch("app.services.generation_service.asyncio.create_task"):
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

    with patch("app.services.generation_service.asyncio.create_task"):
        await service.generate(_CLIENT_ID, "review_due")

    call_args = mock_draft_svc.create.call_args[0][0]
    assert isinstance(call_args, MessageDraftCreate)
    assert call_args.client_id == _CLIENT_ID
    assert call_args.trigger_type == "review_due"
