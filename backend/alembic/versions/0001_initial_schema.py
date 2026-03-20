"""initial_schema

Revision ID: 0001
Revises: 
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- advisor ---
    op.create_table(
        "advisor",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("default_tone", sa.String(50), nullable=False, server_default="professional"),
        sa.UniqueConstraint("email", name="uq_advisor_email"),
    )

    # --- client ---
    op.create_table(
        "client",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("advisor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=False),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["advisor_id"], ["advisor.id"], ondelete="CASCADE", name="fk_client_advisor_id"
        ),
    )

    # --- financial_profile ---
    op.create_table(
        "financial_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_aum", sa.Numeric(15, 2), nullable=True),
        sa.Column("ytd_return_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("risk_profile", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"], ["client.id"], ondelete="CASCADE", name="fk_financial_profile_client_id"
        ),
        sa.UniqueConstraint("client_id", name="uq_financial_profile_client_id"),
    )

    # --- interaction ---
    op.create_table(
        "interaction",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(50), nullable=False, server_default="voice_memo"),
        sa.Column("raw_transcript", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["client.id"], ondelete="CASCADE", name="fk_interaction_client_id"
        ),
    )

    # --- client_context  (depends on interaction for source_interaction_id FK) ---
    op.create_table(
        "client_context",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.Enum("personal_interest", "financial_goal", "family_event", "risk_tolerance", name="context_category"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_interaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"], ["client.id"], ondelete="CASCADE", name="fk_client_context_client_id"
        ),
        sa.ForeignKeyConstraint(
            ["source_interaction_id"],
            ["interaction.id"],
            ondelete="SET NULL",
            name="fk_client_context_source_interaction_id",
        ),
    )

    # --- message_draft ---
    op.create_table(
        "message_draft",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_type", sa.String(100), nullable=False),
        sa.Column("generated_content", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("pending", "sent", name="draft_status"), nullable=False, server_default="pending"),
        sa.ForeignKeyConstraint(
            ["client_id"], ["client.id"], ondelete="CASCADE", name="fk_message_draft_client_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("message_draft")
    op.drop_table("client_context")
    op.drop_table("interaction")
    op.drop_table("financial_profile")
    op.drop_table("client")
    op.drop_table("advisor")

    op.execute("DROP TYPE IF EXISTS draft_status")
    op.execute("DROP TYPE IF EXISTS context_category")
