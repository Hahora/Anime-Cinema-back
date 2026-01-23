"""create message_edit_history table

Revision ID: a57d6feed058
Revises: 09138455048c
Create Date: 2026-01-17 16:54:49.871091

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a57d6feed058'
down_revision: Union[str, Sequence[str], None] = '09138455048c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_edit_history",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="CASCADE")),
        sa.Column("old_content", sa.Text, nullable=False),
        sa.Column("new_content", sa.Text, nullable=False),
        sa.Column("edited_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("edited_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("message_edit_history")
