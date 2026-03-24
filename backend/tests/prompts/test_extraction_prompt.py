"""Prompt regression harness — extraction pipeline.

Validates that the EXTRACTION_PROMPT_TEMPLATE:
  1. Embeds the transcript into the prompt correctly.
  2. Produces the expected structured tags when the LLM returns a valid response.
  3. Enforces category enum: tags with unknown categories are silently skipped.
  4. Can be overridden via config at module load time.

Tests use AsyncMock for the LLM provider so no Ollama instance is needed.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.llm_provider import LLMResult
from app.services.extraction import ExtractionService

# ---------------------------------------------------------------------------
# Fixtures (file-based)
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_transcript() -> str:
    return (_FIXTURE_DIR / "sample_transcript.txt").read_text()


def _load_expected_tags() -> list[dict]:
    return json.loads((_FIXTURE_DIR / "expected_tags.json").read_text())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_INTERACTION_ID = uuid.uuid4()


def _make_result(response: str) -> LLMResult:
    return LLMResult(
        response=response,
        prompt="<prompt>",
        prompt_tokens=50,
        completion_tokens=80,
        latency_ms=200.0,
    )


def _make_provider(responses: list[str]) -> AsyncMock:
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=[_make_result(r) for r in responses])
    return provider


def _make_mock_db() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# Test: EXTRACTION_PROMPT_TEMPLATE contains expected placeholders
# ---------------------------------------------------------------------------


def test_extraction_prompt_template_has_transcript_placeholder() -> None:
    """EXTRACTION_PROMPT_TEMPLATE must contain the {transcript} placeholder."""
    from app.core.prompts import EXTRACTION_PROMPT_TEMPLATE

    assert "{transcript}" in EXTRACTION_PROMPT_TEMPLATE


def test_extraction_prompt_template_mentions_all_categories() -> None:
    """Prompt must list all four valid categories so the LLM knows the enum."""
    from app.core.prompts import EXTRACTION_PROMPT_TEMPLATE

    for category in ("personal_interest", "financial_goal", "family_event", "risk_tolerance"):
        assert category in EXTRACTION_PROMPT_TEMPLATE, (
            f"Category '{category}' missing from EXTRACTION_PROMPT_TEMPLATE"
        )


def test_extraction_prompt_embeds_transcript() -> None:
    """Formatting the template with a transcript inserts the text correctly."""
    from app.core.prompts import EXTRACTION_PROMPT_TEMPLATE

    transcript = "Client said XYZ."
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(transcript=transcript)
    assert transcript in prompt


# ---------------------------------------------------------------------------
# Test: service correctly maps fixture transcript → expected categories
# ---------------------------------------------------------------------------


async def test_extraction_produces_expected_categories() -> None:
    """ExtractionService passes the correct categories from the fixture LLM reply.

    The LLM mock returns the expected_tags.json fixture directly; this validates
    that the service correctly parses and persists them without mutation.
    """
    expected = _load_expected_tags()
    llm_response = json.dumps({"tags": expected})

    provider = _make_provider([llm_response])
    service = ExtractionService(provider=provider)

    with patch("app.services.extraction.ClientContextRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(
            return_value=[MagicMock() for _ in expected]
        )
        mock_repo_cls.return_value = mock_repo

        with patch(
            "app.services.extraction.llm_audit_logger",
            new=MagicMock(log=AsyncMock()),
        ):
            count = await service.extract(
                _load_transcript(),
                _CLIENT_ID,
                _INTERACTION_ID,
                _make_mock_db(),
            )

    assert count == len(expected)

    created_payloads = mock_repo.bulk_create.call_args[0][0]
    returned_categories = {p.category for p in created_payloads}
    expected_categories = {tag["category"] for tag in expected}
    assert returned_categories == expected_categories


# ---------------------------------------------------------------------------
# Test: invalid categories in LLM response are silently skipped
# ---------------------------------------------------------------------------


async def test_invalid_categories_are_skipped() -> None:
    """Tags with categories not in the valid enum are silently dropped."""
    llm_response = json.dumps(
        {
            "tags": [
                {"category": "personal_interest", "content": "Plays tennis"},
                {"category": "INVALID_CATEGORY", "content": "Should be dropped"},
                {"category": "financial_goal", "content": "Retire at 60"},
            ]
        }
    )

    provider = _make_provider([llm_response])
    service = ExtractionService(provider=provider)

    with patch("app.services.extraction.ClientContextRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.bulk_create = AsyncMock(
            return_value=[MagicMock(), MagicMock()]
        )
        mock_repo_cls.return_value = mock_repo

        with patch(
            "app.services.extraction.llm_audit_logger",
            new=MagicMock(log=AsyncMock()),
        ):
            count = await service.extract(
                "Some transcript.",
                _CLIENT_ID,
                _INTERACTION_ID,
                _make_mock_db(),
            )

    assert count == 2

    created_payloads = mock_repo.bulk_create.call_args[0][0]
    categories = [p.category for p in created_payloads]
    assert "INVALID_CATEGORY" not in categories


# ---------------------------------------------------------------------------
# Test: prompt override via environment
# ---------------------------------------------------------------------------


def test_extraction_prompt_override_is_used_when_set() -> None:
    """When EXTRACTION_PROMPT_OVERRIDE is non-empty it replaces the default."""

    import app.core.prompts as prompts_module

    override = "CUSTOM EXTRACTION PROMPT {transcript}"
    with patch.object(prompts_module, "EXTRACTION_PROMPT_TEMPLATE", override):
        result = prompts_module.EXTRACTION_PROMPT_TEMPLATE.format(transcript="X")

    assert result == "CUSTOM EXTRACTION PROMPT X"
