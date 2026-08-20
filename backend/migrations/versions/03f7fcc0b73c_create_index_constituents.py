"""create index constituents

Revision ID: 03f7fcc0b73c
Revises: 324bbc9aff60
Create Date: 2026-08-18 23:42:06.891786
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "03f7fcc0b73c"
down_revision: str | Sequence[str] | None = "324bbc9aff60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the index constituents table."""

    op.create_table(
        "index_constituents",
        sa.Column(
            "index_symbol",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "ticker",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_index_constituents_index_active",
        "index_constituents",
        [
            "index_symbol",
            "is_active",
        ],
        unique=False,
    )

    op.create_index(
        "ix_index_constituents_index_ticker",
        "index_constituents",
        [
            "index_symbol",
            "ticker",
        ],
        unique=True,
    )


def downgrade() -> None:
    """Drop the index constituents table."""

    op.drop_index(
        "ix_index_constituents_index_ticker",
        table_name="index_constituents",
    )

    op.drop_index(
        "ix_index_constituents_index_active",
        table_name="index_constituents",
    )

    op.drop_table(
        "index_constituents",
    )