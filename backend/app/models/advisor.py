import uuid
from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Advisor(Base):
    __tablename__ = "advisors"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    default_tone: Mapped[str] = mapped_column(String(50), nullable=False, default="professional")

    clients: Mapped[list["Client"]] = relationship(
        back_populates="advisor", cascade="all, delete-orphan"
    )
