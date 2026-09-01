"""Add immutable versioned Forward Paper evidence.

Revision ID: e23f1a2b3c4d
Revises: c5e8f1a2b3d4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e23f1a2b3c4d"
down_revision: str | Sequence[str] | None = "c5e8f1a2b3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_validation_records",
        sa.Column("entry_evidence_schema_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "paper_validation_records",
        sa.Column("entry_evidence", sa.JSON(), nullable=True),
    )
    op.add_column(
        "paper_validation_records",
        sa.Column("exit_evidence_schema_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "paper_validation_records",
        sa.Column("exit_evidence", sa.JSON(), nullable=True),
    )
    op.create_check_constraint(
        "ck_paper_entry_evidence_version",
        "paper_validation_records",
        "entry_evidence_schema_version IS NULL OR entry_evidence_schema_version = 1",
    )
    op.create_check_constraint(
        "ck_paper_exit_evidence_version",
        "paper_validation_records",
        "exit_evidence_schema_version IS NULL OR exit_evidence_schema_version = 1",
    )
    op.execute(
        """
        CREATE FUNCTION prevent_paper_evidence_rewrite() RETURNS trigger AS $$
        BEGIN
          IF OLD.entry_evidence IS NOT NULL AND
             (NEW.entry_evidence::jsonb IS DISTINCT FROM OLD.entry_evidence::jsonb OR
              NEW.entry_evidence_schema_version IS DISTINCT FROM OLD.entry_evidence_schema_version)
          THEN RAISE EXCEPTION 'entry evidence is immutable'; END IF;
          IF OLD.exit_evidence IS NOT NULL AND
             (NEW.exit_evidence::jsonb IS DISTINCT FROM OLD.exit_evidence::jsonb OR
              NEW.exit_evidence_schema_version IS DISTINCT FROM OLD.exit_evidence_schema_version)
          THEN RAISE EXCEPTION 'exit evidence is immutable'; END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER paper_evidence_immutable
        BEFORE UPDATE ON paper_validation_records
        FOR EACH ROW EXECUTE FUNCTION prevent_paper_evidence_rewrite();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS paper_evidence_immutable ON paper_validation_records")
    op.execute("DROP FUNCTION IF EXISTS prevent_paper_evidence_rewrite()")
    op.drop_constraint(
        "ck_paper_exit_evidence_version", "paper_validation_records", type_="check"
    )
    op.drop_constraint(
        "ck_paper_entry_evidence_version", "paper_validation_records", type_="check"
    )
    op.drop_column("paper_validation_records", "exit_evidence")
    op.drop_column("paper_validation_records", "exit_evidence_schema_version")
    op.drop_column("paper_validation_records", "entry_evidence")
    op.drop_column("paper_validation_records", "entry_evidence_schema_version")
