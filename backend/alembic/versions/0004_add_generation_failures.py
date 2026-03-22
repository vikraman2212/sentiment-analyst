"""add_generation_failures_table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_failures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("trigger_type", sa.String(100), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=False),
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(
            ["client_id"], ["clients.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generation_failures_client_id",
        "generation_failures",
        ["client_id"],
    )
    op.create_index(
        "ix_generation_failures_resolved",
        "generation_failures",
        ["resolved"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_failures_resolved", table_name="generation_failures")
    op.drop_index("ix_generation_failures_client_id", table_name="generation_failures")
    op.drop_table("generation_failures")
