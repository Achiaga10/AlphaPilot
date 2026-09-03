"""Allow prospective Paper entry-safety evidence schema v2.

Revision ID: b4e2c8a1d903
Revises: c1d4e7f9a250
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4e2c8a1d903"
down_revision: str | Sequence[str] | None = "c1d4e7f9a250"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_paper_entry_evidence_version",
        "paper_validation_records",
        type_="check",
    )
    op.create_check_constraint(
        "ck_paper_entry_evidence_version",
        "paper_validation_records",
        "entry_evidence_schema_version IS NULL OR entry_evidence_schema_version IN (1, 2)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_paper_entry_evidence_version",
        "paper_validation_records",
        type_="check",
    )
    op.create_check_constraint(
        "ck_paper_entry_evidence_version",
        "paper_validation_records",
        "entry_evidence_schema_version IS NULL OR entry_evidence_schema_version = 1",
    )
