from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.advisor import Advisor
    from app.models.client_context import ClientContext
    from app.models.financial_profile import FinancialProfile
    from app.models.generation_failure import GenerationFailure
    from app.models.interaction import Interaction
    from app.models.message_draft import MessageDraft


class Client(Base):
    __tablename__ = "client"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advisor.id", ondelete="CASCADE"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    advisor: Mapped[Advisor] = relationship(back_populates="clients")
    financial_profile: Mapped[FinancialProfile] = relationship(
        back_populates="client", cascade="all, delete-orphan", uselist=False
    )
    context_tags: Mapped[list[ClientContext]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    interactions: Mapped[list[Interaction]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    message_drafts: Mapped[list[MessageDraft]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    generation_failures: Mapped[list[GenerationFailure]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
