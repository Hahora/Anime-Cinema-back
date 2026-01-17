"""create chat_participants table

Revision ID: 209360cc6442
Revises: 28e13e773780
Create Date: 2026-01-17 16:53:04.745218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '209360cc6442'
down_revision: Union[str, Sequence[str], None] = '28e13e773780'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_participants",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("chat_id", sa.Integer, sa.ForeignKey("chats.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("joined_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_read_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("restored_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("chat_participants")
