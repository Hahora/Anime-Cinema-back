"""create users table

Revision ID: 3854834d3c61
Revises: 
Create Date: 2026-01-17 16:39:12.767217

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = '3854834d3c61'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(500), server_default="/static/images/avatar.webp"),
        sa.Column("cover_url", sa.String(500), server_default="/static/images/cover.webp"),
        sa.Column("bio", sa.Text, server_default="Любитель аниме 🎌"),
        sa.Column("message_privacy", sa.String(20), server_default="all"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_table("users")
