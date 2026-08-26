"""add custom company tracking

Revision ID: 6e1464ffb227
Revises: 03f7fcc0b73c
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6e1464ffb227"
down_revision: str | Sequence[str] | None = "03f7fcc0b73c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "is_custom_tracked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "is_custom_tracked")
