from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.client import Client


class Advisor(Base):
    __tablename__ = "advisor"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    default_tone: Mapped[str] = mapped_column(String(50), nullable=False, default="professional")

    clients: Mapped[list[Client]] = relationship(
        back_populates="advisor", cascade="all, delete-orphan"
    )
