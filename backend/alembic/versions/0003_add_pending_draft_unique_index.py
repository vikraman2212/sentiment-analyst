"""add_pending_draft_unique_index

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_message_draft_client_pending",
        "message_draft",
        ["client_id"],
        unique=True,
        postgresql_where=text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_message_draft_client_pending", table_name="message_draft")
