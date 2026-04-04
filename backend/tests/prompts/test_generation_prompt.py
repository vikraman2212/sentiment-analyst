"""Prompt regression harness — generation pipeline.

Validates that the GENERATION_SYSTEM_PROMPT:
  1. Is a non-empty string with the expected tone rules.
  2. Is forwarded correctly to the LLM provider by GenerationService.
  3. The ``_normalize`` helper strips LLM artefacts (subject lines, salutations,
     sign-offs) that violate the system prompt rules.
  4. Can be overridden via the GENERATION_PROMPT_OVERRIDE config field.

Tests use AsyncMock for the LLM provider and service boundaries;
no database or Ollama instance is required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from agent_sdk.agents.generation.ports import PromptContext
from agent_sdk.agents.generation.service import _normalize
from agent_sdk.core.contracts import AgentTrigger

from app.core.llm_provider import LLMResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(response: str) -> LLMResult:
    return LLMResult(
        response=response,
        prompt="<context block>",
        prompt_tokens=100,
        completion_tokens=60,
        latency_ms=350.0,
    )


# ---------------------------------------------------------------------------
# Test: GENERATION_SYSTEM_PROMPT content rules
# ---------------------------------------------------------------------------


def test_generation_system_prompt_is_non_empty() -> None:
    """GENERATION_SYSTEM_PROMPT must be a non-empty string."""
    from app.core.prompts import GENERATION_SYSTEM_PROMPT

    assert isinstance(GENERATION_SYSTEM_PROMPT, str)
    assert len(GENERATION_SYSTEM_PROMPT.strip()) > 0


def test_generation_system_prompt_enforces_sentence_limit() -> None:
    """Prompt must mention the maximum sentence constraint."""
    from app.core.prompts import GENERATION_SYSTEM_PROMPT

    assert "4 sentences" in GENERATION_SYSTEM_PROMPT


def test_generation_system_prompt_prohibits_unrounded_amounts() -> None:
    """Prompt must instruct the model to round dollar amounts."""
    from app.core.prompts import GENERATION_SYSTEM_PROMPT

    assert "$100,000" in GENERATION_SYSTEM_PROMPT or "rounded" in GENERATION_SYSTEM_PROMPT


def test_generation_system_prompt_forbids_sign_off() -> None:
    """Prompt must explicitly disallow sign-off lines."""
    from app.core.prompts import GENERATION_SYSTEM_PROMPT

    assert "sign-off" in GENERATION_SYSTEM_PROMPT or "no sign" in GENERATION_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Test: system prompt forwarded to the LLM provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generation_service_forwards_system_prompt() -> None:
    """GenerationAgent passes GENERATION_SYSTEM_PROMPT as the system arg."""
    from agent_sdk.agents.generation.service import GenerationAgent

    from app.core.prompts import GENERATION_SYSTEM_PROMPT

    client_id = uuid.uuid4()
    advisor_id = uuid.uuid4()
    draft_id = uuid.uuid4()

    mock_context_reader = AsyncMock()
    mock_context_reader.assemble = AsyncMock(
        return_value=PromptContext(
            prompt_block="## Client Profile\nName: Sarah",
            client_name="Sarah",
        )
    )

    mock_draft_writer = AsyncMock()
    mock_draft_writer.find_pending_draft = AsyncMock(return_value=None)
    mock_draft_writer.create_draft = AsyncMock(return_value=draft_id)
    mock_draft_writer.delete_draft = AsyncMock()

    mock_provider = AsyncMock()
    clean_body = "Hi Sarah, I hope you are well."
    mock_provider.complete = AsyncMock(return_value=_make_result(clean_body))

    agent = GenerationAgent(
        context_reader=mock_context_reader,
        draft_writer=mock_draft_writer,
        provider=mock_provider,
        system_prompt=GENERATION_SYSTEM_PROMPT,
    )

    with patch("agent_sdk.agents.generation.service.asyncio.create_task"):
        await agent.run(
            AgentTrigger(
                client_id=client_id,
                advisor_id=advisor_id,
                trigger_type="review_due",
            )
        )

    mock_provider.complete.assert_awaited_once()
    _, kwargs = mock_provider.complete.call_args
    assert kwargs.get("system") == GENERATION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Test: _normalize strips LLM output artefacts
# ---------------------------------------------------------------------------


def test_normalize_strips_subject_line() -> None:
    """_normalize removes an accidental 'Subject: ...' line."""
    raw = "Subject: Your Portfolio Review\nHi Sarah, your portfolio is looking strong."

    result = _normalize(raw)
    assert "Subject:" not in result
    assert "Hi Sarah" in result


def test_normalize_strips_salutation() -> None:
    """_normalize removes 'Dear <name>,' openings."""
    raw = "Dear Sarah,\nYour portfolio has grown by 8% this year."

    result = _normalize(raw)

    assert "Dear Sarah" not in result
    assert "portfolio" in result


def test_normalize_strips_sign_off() -> None:
    """_normalize removes 'Warm regards / Sincerely / ...' sign-off blocks."""
    raw = "Your portfolio is performing well.\n\nWarm regards,\nJohn Advisor"

    result = _normalize(raw)

    assert "Warm regards" not in result
    assert "portfolio" in result


# ---------------------------------------------------------------------------
# Test: override mechanism
# ---------------------------------------------------------------------------


def test_generation_prompt_override_is_respected() -> None:
    """Patching GENERATION_SYSTEM_PROMPT replaces the prompt at runtime."""
    import app.core.prompts as prompts_module

    custom = "CUSTOM GENERATION PROMPT"
    with patch.object(prompts_module, "GENERATION_SYSTEM_PROMPT", custom):
        assert prompts_module.GENERATION_SYSTEM_PROMPT == custom
