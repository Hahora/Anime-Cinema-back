"""create favorites table

Revision ID: 554dc3a89d46
Revises: 3854834d3c61
Create Date: 2026-01-17 16:43:43.082467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '554dc3a89d46'
down_revision: Union[str, Sequence[str], None] = '3854834d3c61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("anime_id", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(255)),
        sa.Column("poster", sa.String(500)),
        sa.Column("year", sa.Integer),
        sa.Column("rating", sa.Float),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=func.now()),
        sa.UniqueConstraint("user_id", "anime_id", name="uq_user_anime_favorite"),
    )
    op.create_index("idx_favorites_user_added", "favorites", ["user_id", "added_at"])


def downgrade() -> None:
    op.drop_table("favorites")
