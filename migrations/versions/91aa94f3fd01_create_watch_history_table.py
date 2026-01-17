"""create watch_history table

Revision ID: 91aa94f3fd01
Revises: c21e4c2075f5
Create Date: 2026-01-17 16:46:06.715797

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '91aa94f3fd01'
down_revision: Union[str, Sequence[str], None] = 'c21e4c2075f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watch_history",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("anime_id", sa.String(50), nullable=False, index=True),
        sa.Column("episode_num", sa.Integer, nullable=False),
        sa.Column("progress_seconds", sa.Integer, server_default="0"),
        sa.Column("duration_seconds", sa.Integer, server_default="0"),
        sa.Column("title", sa.String(255)),
        sa.Column("poster", sa.String(500)),
        sa.Column("translation_id", sa.String(50)),
        sa.Column("watched_at", sa.DateTime(timezone=True), server_default=func.now()),
    )
    op.create_index("idx_history_user_watched", "watch_history", ["user_id", "watched_at"])


def downgrade() -> None:
    op.drop_table("watch_history")
