"""create friendships table

Revision ID: 392349af8917
Revises: 91aa94f3fd01
Create Date: 2026-01-17 16:46:54.687375

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = '392349af8917'
down_revision: Union[str, Sequence[str], None] = '91aa94f3fd01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("friend_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=func.now()),
        sa.UniqueConstraint("user_id", "friend_id", name="unique_friendship"),
    )


def downgrade() -> None:
    op.drop_table("friendships")
