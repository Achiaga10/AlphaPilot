"""Make paper execution timestamps timezone-aware.

Revision ID: c5e8f1a2b3d4
Revises: a18c4d9e2f70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5e8f1a2b3d4"
down_revision: str | Sequence[str] | None = "a18c4d9e2f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "paper_validation_records",
        "actual_entry_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="actual_entry_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "paper_validation_records",
        "actual_exit_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="actual_exit_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "paper_validation_records",
        "actual_exit_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="actual_exit_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "paper_validation_records",
        "actual_entry_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="actual_entry_at AT TIME ZONE 'UTC'",
    )
