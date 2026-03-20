import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CONTEXT_CATEGORIES = ("personal_interest", "financial_goal", "family_event", "risk_tolerance")


class ClientContext(Base):
    __tablename__ = "client_context"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(
        Enum(*CONTEXT_CATEGORIES, name="context_category"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_interaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("interactions.id", ondelete="SET NULL"), nullable=True
    )

    client: Mapped["Client"] = relationship(back_populates="context_tags")
    source_interaction: Mapped["Interaction | None"] = relationship()


from app.models.client import Client  # noqa: E402
from app.models.interaction import Interaction  # noqa: E402
