import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    total_aum: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    ytd_return_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3), nullable=True
    )
    risk_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)

    client: Mapped["Client"] = relationship(back_populates="financial_profile")


from app.models.client import Client  # noqa: E402
