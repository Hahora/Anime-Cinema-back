"""create chats table

Revision ID: 28e13e773780
Revises: a71c4091cc61
Create Date: 2026-01-17 16:48:37.370655

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '28e13e773780'
down_revision: Union[str, Sequence[str], None] = 'a71c4091cc61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chats",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("type", sa.String, server_default="private"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("chats")
