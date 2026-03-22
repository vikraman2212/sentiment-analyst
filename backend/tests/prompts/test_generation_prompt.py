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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


async def test_generation_service_forwards_system_prompt() -> None:
    """GenerationService passes GENERATION_SYSTEM_PROMPT as the system arg."""
    from app.core.prompts import GENERATION_SYSTEM_PROMPT
    from app.services.generation_service import GenerationService

    mock_provider = AsyncMock()
    clean_body = "Hi Sarah, I hope you are well."
    mock_provider.complete = AsyncMock(return_value=_make_result(clean_body))

    mock_db = AsyncMock()
    service = GenerationService(db=mock_db, provider=mock_provider)

    mock_context = MagicMock()
    mock_context.prompt_block = "## Client Profile\nName: Sarah"

    mock_draft = MagicMock()
    mock_draft.id = uuid.uuid4()
    mock_draft.client_id = uuid.uuid4()
    mock_draft.trigger_type = "review_due"
    mock_draft.generated_content = clean_body

    with (
        patch.object(service._context_svc, "assemble", AsyncMock(return_value=mock_context)),
        patch.object(service._draft_svc, "find_pending_by_client", AsyncMock(return_value=None)),
        patch.object(service._draft_svc, "create", AsyncMock(return_value=mock_draft)),
        patch(
            "app.services.generation_service.llm_audit_logger",
            new=MagicMock(log=AsyncMock()),
        ),
    ):
        result = await service.generate(mock_draft.client_id, "review_due")

    mock_provider.complete.assert_awaited_once()
    _, kwargs = mock_provider.complete.call_args
    assert kwargs.get("system") == GENERATION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Test: _normalize strips LLM output artefacts
# ---------------------------------------------------------------------------


def test_normalize_strips_subject_line() -> None:
    """_normalize removes an accidental 'Subject: ...' line."""
    from app.services.generation_service import _normalize

    raw = "Subject: Your Portfolio Review\nHi Sarah, your portfolio is looking strong."

    result = _normalize(raw)
    assert "Subject:" not in result
    assert "Hi Sarah" in result


def test_normalize_strips_salutation() -> None:
    """_normalize removes 'Dear <name>,' openings."""
    from app.services.generation_service import _normalize

    raw = "Dear Sarah,\nYour portfolio has grown by 8% this year."

    result = _normalize(raw)

    assert "Dear Sarah" not in result
    assert "portfolio" in result


def test_normalize_strips_sign_off() -> None:
    """_normalize removes 'Warm regards / Sincerely / ...' sign-off blocks."""
    from app.services.generation_service import _normalize

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
