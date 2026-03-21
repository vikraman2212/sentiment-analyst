"""Pydantic schemas for assembled client context payloads."""

import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.client_context import ClientContextResponse


class FinancialSummary(BaseModel):
    """Null-safe snapshot of a client's financial profile."""

    total_aum: Decimal | None = None
    ytd_return_pct: Decimal | None = None
    risk_profile: str | None = None


class AssembledContext(BaseModel):
    """Full context payload assembled for a single client prompt.

    Built by ContextAssemblyService and consumed directly by the
    generation pipeline — never hydrated from an ORM model instance.
    """

    client_id: uuid.UUID
    client_name: str
    financial_summary: FinancialSummary
    context_tags: list[ClientContextResponse]
    prompt_block: str
