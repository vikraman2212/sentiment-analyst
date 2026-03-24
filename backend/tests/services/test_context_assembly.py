"""Unit tests for ContextAssemblyService.

All repositories and DB session are mocked — no network or database required.
Tests follow AAA (Arrange → Act → Assert) with blank lines between sections.
"""

import uuid
from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app.services.context_assembly as _context_assembly_mod
from app.core.exceptions import NotFoundError
from app.services.context_assembly import ContextAssemblyService
from tests.services.conftest import make_span_exporter

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = uuid.uuid4()
_ADVISOR_ID = uuid.uuid4()


def _make_client(
    client_id: uuid.UUID = _CLIENT_ID,
    first_name: str = "Jane",
    last_name: str = "Smith",
    next_review_date: date | None = None,
) -> MagicMock:
    c = MagicMock()
    c.id = client_id
    c.first_name = first_name
    c.last_name = last_name
    c.next_review_date = next_review_date
    return c


def _make_profile(
    total_aum: Decimal | None = Decimal("500000.00"),
    ytd_return_pct: Decimal | None = Decimal("7.250"),
    risk_profile: str | None = "moderate",
) -> MagicMock:
    p = MagicMock()
    p.total_aum = total_aum
    p.ytd_return_pct = ytd_return_pct
    p.risk_profile = risk_profile
    return p


def _make_tag(category: str, content: str) -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.client_id = _CLIENT_ID
    t.category = category
    t.content = content
    t.source_interaction_id = None
    return t


def _make_service() -> tuple[ContextAssemblyService, dict]:
    """Return service + dict of the three underlying repo mocks."""
    db = AsyncMock()
    service = ContextAssemblyService(db)
    mocks: dict = {
        "client": AsyncMock(),
        "profile": AsyncMock(),
        "context": AsyncMock(),
    }
    service._client_repo = mocks["client"]
    service._profile_repo = mocks["profile"]
    service._context_repo = mocks["context"]
    return service, mocks


# ---------------------------------------------------------------------------
# assemble() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assemble_happy_path() -> None:
    """All data present → prompt_block contains AUM value and category headers."""
    service, mocks = _make_service()
    tags = [
        _make_tag("personal_interest", "Enjoys golf"),
        _make_tag("financial_goal", "Retire at 60"),
    ]
    mocks["client"].get_by_id = AsyncMock(return_value=_make_client())
    mocks["profile"].get_by_client_id = AsyncMock(return_value=_make_profile())
    mocks["context"].list_by_client = AsyncMock(return_value=tags)

    result = await service.assemble(_CLIENT_ID)

    assert result.client_id == _CLIENT_ID
    assert result.client_name == "Jane Smith"
    assert result.financial_summary.total_aum == Decimal("500000.00")
    assert result.financial_summary.risk_profile == "moderate"
    assert len(result.context_tags) == 2
    assert "$500,000.00" in result.prompt_block
    assert "Personal Interests" in result.prompt_block
    assert "Financial Goals" in result.prompt_block
    assert "Enjoys golf" in result.prompt_block


@pytest.mark.asyncio
async def test_assemble_missing_financial_profile() -> None:
    """No financial profile → no crash; prompt_block shows 'Not available'."""
    service, mocks = _make_service()
    mocks["client"].get_by_id = AsyncMock(return_value=_make_client())
    mocks["profile"].get_by_client_id = AsyncMock(return_value=None)
    mocks["context"].list_by_client = AsyncMock(return_value=[])

    result = await service.assemble(_CLIENT_ID)

    assert result.financial_summary.total_aum is None
    assert result.financial_summary.risk_profile is None
    assert "Not available" in result.prompt_block
    assert "Not specified" in result.prompt_block


@pytest.mark.asyncio
async def test_assemble_empty_context_tags() -> None:
    """No context tags → valid AssembledContext, no category sections in prompt."""
    service, mocks = _make_service()
    mocks["client"].get_by_id = AsyncMock(return_value=_make_client())
    mocks["profile"].get_by_client_id = AsyncMock(return_value=_make_profile())
    mocks["context"].list_by_client = AsyncMock(return_value=[])

    result = await service.assemble(_CLIENT_ID)

    assert result.context_tags == []
    assert "Personal Interests" not in result.prompt_block
    assert "Financial Goals" not in result.prompt_block
    assert "Recent Context Notes" not in result.prompt_block


@pytest.mark.asyncio
async def test_assemble_client_not_found() -> None:
    """Client does not exist → NotFoundError raised."""
    service, mocks = _make_service()
    mocks["client"].get_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.assemble(_CLIENT_ID)


# ---------------------------------------------------------------------------
# list_needing_review() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_needing_review_returns_assembled_contexts() -> None:
    """Two clients needing review → two AssembledContext objects returned."""
    service, mocks = _make_service()
    client_a = _make_client(client_id=uuid.uuid4(), first_name="Alice", last_name="A")
    client_b = _make_client(client_id=uuid.uuid4(), first_name="Bob", last_name="B")

    mocks["client"].list_needing_review = AsyncMock(return_value=[client_a, client_b])
    mocks["client"].get_by_id = AsyncMock(side_effect=[client_a, client_b])
    mocks["profile"].get_by_client_id = AsyncMock(return_value=None)
    mocks["context"].list_by_client = AsyncMock(return_value=[])

    results = await service.list_needing_review(_ADVISOR_ID)

    assert len(results) == 2
    assert results[0].client_name == "Alice A"
    assert results[1].client_name == "Bob B"
    mocks["client"].list_needing_review.assert_awaited_once()
    call_args = mocks["client"].list_needing_review.call_args
    cutoff_passed: date = call_args[0][1]
    assert cutoff_passed == date.today() + timedelta(days=14)


@pytest.mark.asyncio
async def test_list_needing_review_no_clients() -> None:
    """No clients due for review → empty list returned without error."""
    service, mocks = _make_service()
    mocks["client"].list_needing_review = AsyncMock(return_value=[])

    results = await service.list_needing_review(_ADVISOR_ID)

    assert results == []


# ---------------------------------------------------------------------------
# Span tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Fixture: wire a fresh in-memory exporter into the context assembly tracer."""
    exporter, provider = make_span_exporter()
    original = _context_assembly_mod._tracer
    _context_assembly_mod._tracer = provider.get_tracer(__name__)
    yield exporter
    _context_assembly_mod._tracer = original


@pytest.mark.asyncio
async def test_assemble_emits_context_assembly_span(
    span_exporter: InMemorySpanExporter,
) -> None:
    """Happy path: a ``context.assembly`` span is recorded with client_id and tag_count."""
    service, mocks = _make_service()
    tags = [
        _make_tag("personal_interest", "Enjoys tennis"),
        _make_tag("financial_goal", "Retire early"),
    ]
    mocks["client"].get_by_id = AsyncMock(return_value=_make_client())
    mocks["profile"].get_by_client_id = AsyncMock(return_value=_make_profile())
    mocks["context"].list_by_client = AsyncMock(return_value=tags)

    await service.assemble(_CLIENT_ID)

    spans = span_exporter.get_finished_spans()
    assembly_spans = [s for s in spans if s.name == "context.assembly"]
    assert len(assembly_spans) == 1
    span = assembly_spans[0]
    attrs = cast(dict[str, object], span.attributes or {})
    assert attrs["client_id"] == str(_CLIENT_ID)
    assert attrs["tag_count"] == 2


@pytest.mark.asyncio
async def test_assemble_span_tag_count_zero_when_no_tags(
    span_exporter: InMemorySpanExporter,
) -> None:
    """No context tags → context.assembly span records tag_count=0."""
    service, mocks = _make_service()
    mocks["client"].get_by_id = AsyncMock(return_value=_make_client())
    mocks["profile"].get_by_client_id = AsyncMock(return_value=None)
    mocks["context"].list_by_client = AsyncMock(return_value=[])

    await service.assemble(_CLIENT_ID)

    spans = span_exporter.get_finished_spans()
    assembly_spans = [s for s in spans if s.name == "context.assembly"]
    assert len(assembly_spans) == 1
    assert cast(dict[str, object], assembly_spans[0].attributes or {})["tag_count"] == 0


@pytest.mark.asyncio
async def test_assemble_span_error_status_on_client_not_found(
    span_exporter: InMemorySpanExporter,
) -> None:
    """Client not found → context.assembly span status is ERROR."""
    from opentelemetry.trace import StatusCode

    service, mocks = _make_service()
    mocks["client"].get_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.assemble(_CLIENT_ID)

    spans = span_exporter.get_finished_spans()
    assembly_spans = [s for s in spans if s.name == "context.assembly"]
    assert len(assembly_spans) == 1
    assert assembly_spans[0].status.status_code == StatusCode.ERROR

