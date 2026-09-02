"""Add immutable entry-time News decision provenance to positions.

Revision ID: f9b2d6e5a031
Revises: e8a1c5d4f920
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9b2d6e5a031"
down_revision: str | Sequence[str] | None = "e8a1c5d4f920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_positions",
        sa.Column("entry_decision_evidence", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_positions", "entry_decision_evidence")
