"""create watched_anime table

Revision ID: c21e4c2075f5
Revises: 554dc3a89d46
Create Date: 2026-01-17 16:44:56.129941

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = 'c21e4c2075f5'
down_revision: Union[str, Sequence[str], None] = '554dc3a89d46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watched_anime",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("anime_id", sa.String(50), nullable=False, index=True),
        sa.Column("episodes_watched", sa.Integer, server_default="0"),
        sa.Column("total_episodes", sa.Integer, server_default="0"),
        sa.Column("is_completed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("title", sa.String(255)),
        sa.Column("poster", sa.String(500)),
        sa.Column("last_watched", sa.DateTime(timezone=True), server_default=func.now()),
        sa.UniqueConstraint("user_id", "anime_id", name="uq_user_anime_watched"),
    )
    op.create_index("idx_watched_user_last", "watched_anime", ["user_id", "last_watched"])


def downgrade() -> None:
    op.drop_table("watched_anime")
