"""Unit tests for GenerationAgent (was GenerationService).

All external deps (LLMProvider, IContextAssembler, IDraftWriter) are mocked.
Tests follow AAA (Arrange -> Act -> Assert).
"""

import uuid
from collections.abc import Generator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import agent_sdk.agents.generation.service as _generation_mod
import pytest
from agent_sdk.agents.generation.ports import PromptContext
from agent_sdk.agents.generation.service import GenerationAgent, _normalize
from agent_sdk.core.contracts import AgentResult, AgentTrigger
from agent_sdk.core.exceptions import GenerationError, LLMProviderError
from agent_sdk.core.llm_provider import LLMResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tests.services.conftest import make_span_exporter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_ADVISOR_ID = uuid.uuid4()
_DRAFT_ID = uuid.uuid4()


def _make_trigger(trigger_type: str = "review_due", force: bool = False) -> AgentTrigger:
    return AgentTrigger(
        client_id=_CLIENT_ID,
        advisor_id=_ADVISOR_ID,
        trigger_type=trigger_type,
        payload={"force": force} if force else {},
    )


def _make_llm_result(response: str) -> LLMResult:
    return LLMResult(
        response=response,
        prompt="<prompt>",
        prompt_tokens=80,
        completion_tokens=40,
        latency_ms=250.0,
    )


def _make_agent(
    provider_response: str | None = None,
    provider_side_effect: Exception | None = None,
    prompt_context: PromptContext | None = None,
    existing_pending_draft_id: uuid.UUID | None = None,
) -> tuple[GenerationAgent, AsyncMock, AsyncMock, AsyncMock]:
    """Build a GenerationAgent with all deps mocked.

    Returns:
        Tuple of (agent, mock_provider, mock_context_reader, mock_draft_writer).
    """
    mock_provider = AsyncMock()
    if provider_side_effect is not None:
        mock_provider.complete = AsyncMock(side_effect=provider_side_effect)
    else:
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_result(provider_response or "Clean email body text.")
        )

    mock_context_reader = AsyncMock()
    mock_context_reader.assemble = AsyncMock(
        return_value=prompt_context
        or PromptContext(
            prompt_block="## Client Profile\nName: Jane Doe",
            client_name="Jane Doe",
        )
    )

    mock_draft_writer = AsyncMock()
    mock_draft_writer.find_pending_draft = AsyncMock(
        return_value=existing_pending_draft_id
    )
    mock_draft_writer.create_draft = AsyncMock(return_value=_DRAFT_ID)
    mock_draft_writer.delete_draft = AsyncMock(return_value=None)

    agent = GenerationAgent(
        context_reader=mock_context_reader,
        draft_writer=mock_draft_writer,
        provider=mock_provider,
    )

    return agent, mock_provider, mock_context_reader, mock_draft_writer


@pytest.fixture(autouse=True)
def patch_background_audit_tasks() -> Generator[None, None, None]:
    """Patch fire-and-forget audit task scheduling to keep tests deterministic."""

    def _discard_task(coro: object) -> MagicMock:
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        return MagicMock()

    with patch(
        "agent_sdk.agents.generation.service.asyncio.create_task",
        side_effect=_discard_task,
    ):
        yield


# ---------------------------------------------------------------------------
# GenerationAgent.run() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_happy_path() -> None:
    """Full pipeline: context assembled, LLM called, draft persisted."""
    email_body = "Hi Jane, just a quick note about your portfolio."
    agent, mock_provider, mock_context_reader, mock_draft_writer = _make_agent(
        provider_response=email_body
    )

    result = await agent.run(_make_trigger())

    assert isinstance(result, AgentResult)
    assert result.success is True
    assert result.output["draft_id"] == str(_DRAFT_ID)
    assert "cached" not in result.output
    mock_context_reader.assemble.assert_awaited_once_with(_CLIENT_ID)
    mock_provider.complete.assert_awaited_once()
    call_kwargs = mock_provider.complete.call_args
    assert call_kwargs.kwargs["model"] is not None
    assert call_kwargs.kwargs["system"] is not None
    mock_draft_writer.create_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_client_not_found_propagates() -> None:
    """NotFoundError from context reader propagates unchanged."""
    from agent_sdk.core.exceptions import NotFoundError

    agent, _, mock_context_reader, _ = _make_agent()
    mock_context_reader.assemble = AsyncMock(
        side_effect=NotFoundError(f"Client {_CLIENT_ID} not found")
    )

    with pytest.raises(NotFoundError):
        await agent.run(_make_trigger())


@pytest.mark.asyncio
async def test_generate_llm_provider_error_raises_generation_error() -> None:
    """LLMProviderError from provider.complete -> GenerationError raised."""
    agent, _, _, _ = _make_agent(
        provider_side_effect=LLMProviderError("Connection refused")
    )

    with pytest.raises(GenerationError, match="LLM provider failed"):
        await agent.run(_make_trigger())


@pytest.mark.asyncio
async def test_generate_passes_prompt_block_to_provider() -> None:
    """The assembled prompt_block is forwarded verbatim as the LLM prompt."""
    custom_block = "## Client Profile\nName: Bob Smith\n## Financial Summary\nAUM: $500k"
    agent, mock_provider, _, _ = _make_agent(
        prompt_context=PromptContext(
            prompt_block=custom_block, client_name="Bob Smith"
        )
    )

    await agent.run(_make_trigger())

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
    """When pending draft exists and force=False, return cached result without LLM."""
    agent, mock_provider, mock_context_reader, mock_draft_writer = _make_agent(
        existing_pending_draft_id=_DRAFT_ID
    )

    result = await agent.run(_make_trigger())

    assert result.success is True
    assert result.output["draft_id"] == str(_DRAFT_ID)
    assert result.output.get("cached") is True
    mock_draft_writer.find_pending_draft.assert_awaited_once_with(_CLIENT_ID)
    mock_provider.complete.assert_not_awaited()
    mock_context_reader.assemble.assert_not_awaited()
    mock_draft_writer.create_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_force_deletes_existing_and_regenerates() -> None:
    """When force=True and a pending draft exists, delete it then run full pipeline."""
    agent, mock_provider, mock_context_reader, mock_draft_writer = _make_agent(
        existing_pending_draft_id=_DRAFT_ID,
        provider_response="Fresh regenerated email.",
    )

    result = await agent.run(_make_trigger(force=True))

    mock_draft_writer.find_pending_draft.assert_awaited_once_with(_CLIENT_ID)
    mock_draft_writer.delete_draft.assert_awaited_once_with(_DRAFT_ID)
    mock_context_reader.assemble.assert_awaited_once_with(_CLIENT_ID)
    mock_provider.complete.assert_awaited_once()
    mock_draft_writer.create_draft.assert_awaited_once()
    assert result.output["draft_id"] == str(_DRAFT_ID)


@pytest.mark.asyncio
async def test_generate_no_pending_proceeds_normally() -> None:
    """When no pending draft exists, the full pipeline runs without calling delete."""
    agent, mock_provider, mock_context_reader, mock_draft_writer = _make_agent()

    result = await agent.run(_make_trigger())

    mock_draft_writer.find_pending_draft.assert_awaited_once_with(_CLIENT_ID)
    mock_draft_writer.delete_draft.assert_not_awaited()
    mock_context_reader.assemble.assert_awaited_once_with(_CLIENT_ID)
    mock_provider.complete.assert_awaited_once()
    mock_draft_writer.create_draft.assert_awaited_once()
    assert result.output["draft_id"] == str(_DRAFT_ID)


# ---------------------------------------------------------------------------
# Span tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Wire a fresh in-memory exporter into the generation agent tracer."""
    exporter, provider = make_span_exporter()
    original = _generation_mod._tracer
    _generation_mod._tracer = provider.get_tracer(__name__)
    yield exporter
    _generation_mod._tracer = original


@pytest.mark.asyncio
async def test_generate_emits_pipeline_span(span_exporter: InMemorySpanExporter) -> None:
    """Happy path: a ``generation.pipeline`` span is recorded with client and trigger attrs."""
    agent, _, _, _ = _make_agent(provider_response="Email body.")

    await agent.run(_make_trigger())

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
    """Happy path: a ``generation.persist`` child span is emitted with draft_id."""
    agent, _, _, _ = _make_agent(provider_response="Email body.")

    await agent.run(_make_trigger())

    spans = span_exporter.get_finished_spans()
    persist_spans = [s for s in spans if s.name == "generation.persist"]
    assert len(persist_spans) == 1
    attributes = cast(dict[str, object], persist_spans[0].attributes or {})
    assert attributes["draft_id"] == str(_DRAFT_ID)


@pytest.mark.asyncio
async def test_generate_pipeline_span_error_on_llm_failure(
    span_exporter: InMemorySpanExporter,
) -> None:
    """LLMProviderError -> pipeline span status is ERROR with exception recorded."""
    from opentelemetry.trace import StatusCode

    agent, _, _, _ = _make_agent(
        provider_side_effect=LLMProviderError("Connection refused")
    )

    with pytest.raises(GenerationError):
        await agent.run(_make_trigger())

    spans = span_exporter.get_finished_spans()
    pipeline_spans = [s for s in spans if s.name == "generation.pipeline"]
    assert len(pipeline_spans) == 1
    assert pipeline_spans[0].status.status_code == StatusCode.ERROR
    assert any(e.name == "exception" for e in pipeline_spans[0].events)
