"""add research data versioning and frozen snapshots

Revision ID: b7a9d4f2c613
Revises: 6e1464ffb227
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7a9d4f2c613"
down_revision: str | Sequence[str] | None = "6e1464ffb227"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_ingestion_batches",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("feed", sa.String(length=50), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("adjustment", sa.String(length=20), nullable=False),
        sa.Column("requested_start", sa.Date(), nullable=False),
        sa.Column("requested_end", sa.Date(), nullable=False),
        sa.Column("benchmark_ticker", sa.String(length=20), nullable=True),
        sa.Column("request_metadata", sa.JSON(), nullable=False),
        sa.Column("symbols_requested", sa.Integer(), nullable=False),
        sa.Column("symbols_succeeded", sa.Integer(), nullable=False),
        sa.Column("symbols_failed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "requested_start <= requested_end",
            name="ck_ingestion_batch_date_range",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_ingestion_batch_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_market_data_ingestion_batches_created",
        "market_data_ingestion_batches",
        ["created_at"],
    )

    op.create_index(
        "ix_market_data_ingestion_batches_provider_feed",
        "market_data_ingestion_batches",
        ["provider", "feed"],
    )

    op.create_table(
        "daily_candle_versions",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("feed", sa.String(length=50), nullable=False),
        sa.Column("provenance_status", sa.String(length=30), nullable=False),
        sa.Column("ingestion_batch_id", sa.UUID(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version_sequence", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(provenance_status = 'LEGACY_UNKNOWN' AND ingestion_batch_id IS NULL) "
            "OR (provenance_status = 'COMPLETE' AND ingestion_batch_id IS NOT NULL)",
            name="ck_candle_version_provenance_batch",
        ),
        sa.CheckConstraint(
            "version_sequence > 0",
            name="ck_candle_version_sequence_positive",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_daily_candle_versions_company_day_sequence",
        "daily_candle_versions",
        ["company_id", "trading_day", "version_sequence"],
        unique=True,
    )

    op.create_index(
        "ix_daily_candle_versions_batch",
        "daily_candle_versions",
        ["ingestion_batch_id"],
    )

    op.create_index(
        "ix_daily_candle_versions_observed",
        "daily_candle_versions",
        ["observed_at"],
    )

    # Preserve the values present at installation without fabricating a source.
    #
    # Reusing the operational UUID is safe and keeps this set-based/idempotent
    # under normal one-time Alembic upgrade semantics.
    op.execute(
        """
        INSERT INTO daily_candle_versions (
            id,
            company_id,
            trading_day,
            open,
            high,
            low,
            close,
            volume,
            provider,
            feed,
            provenance_status,
            ingestion_batch_id,
            observed_at,
            version_sequence
        )
        SELECT
            dc.id,
            dc.company_id,
            dc.trading_day,
            dc.open,
            dc.high,
            dc.low,
            dc.close,
            dc.volume,
            'LEGACY_UNKNOWN',
            'UNKNOWN',
            'LEGACY_UNKNOWN',
            NULL,
            COALESCE(dc.updated_at, dc.created_at, now()),
            1
        FROM daily_candles AS dc
        WHERE NOT EXISTS (
            SELECT 1
            FROM daily_candle_versions AS dcv
            WHERE dcv.company_id = dc.company_id
              AND dcv.trading_day = dc.trading_day
        )
        """
    )

    op.create_table(
        "research_dataset_snapshots",
        sa.Column("label", sa.String(length=150), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "version_watermark_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "provider_expectation",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "feed_expectation",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("adjustment", sa.String(length=20), nullable=False),
        sa.Column("requested_start", sa.Date(), nullable=False),
        sa.Column("requested_end", sa.Date(), nullable=False),
        sa.Column(
            "benchmark_ticker",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "universe_identifier",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("universe_member_count", sa.Integer(), nullable=False),
        sa.Column("company_count", sa.Integer(), nullable=False),
        sa.Column("candle_version_count", sa.BigInteger(), nullable=False),
        sa.Column("minimum_trading_day", sa.Date(), nullable=True),
        sa.Column("maximum_trading_day", sa.Date(), nullable=True),
        sa.Column("universe_sha256", sa.String(length=64), nullable=True),
        sa.Column("dataset_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "provenance_status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column("value_reproducible", sa.Boolean(), nullable=False),
        sa.Column("git_revision", sa.String(length=64), nullable=False),
        sa.Column("git_dirty", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("creation_duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "requested_start <= requested_end",
            name="ck_dataset_snapshot_date_range",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'FINALIZED')",
            name="ck_dataset_snapshot_status",
        ),
        sa.CheckConstraint(
            "provenance_status IN ('COMPLETE', 'LEGACY_PARTIAL', 'UNKNOWN')",
            name="ck_dataset_snapshot_provenance",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_research_dataset_snapshots_created",
        "research_dataset_snapshots",
        ["created_at"],
    )

    op.create_index(
        "ix_research_dataset_snapshots_status",
        "research_dataset_snapshots",
        ["status"],
    )

    op.create_table(
        "research_dataset_universe_members",
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "ticker_at_snapshot",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "company_name_at_snapshot",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "exchange_at_snapshot",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "sector_at_snapshot",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "membership_source",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "role IN ('UNIVERSE', 'BENCHMARK')",
            name="ck_dataset_member_role",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["research_dataset_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "role",
            "ticker_at_snapshot",
            name="uq_dataset_member_role_ticker",
        ),
    )

    op.create_index(
        "ix_dataset_universe_members_snapshot_role",
        "research_dataset_universe_members",
        ["snapshot_id", "role"],
    )

    op.create_index(
        "ix_dataset_universe_members_company",
        "research_dataset_universe_members",
        ["company_id"],
    )

    op.create_table(
        "research_dataset_candle_members",
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("candle_version_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column(
            "ticker_at_snapshot",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candle_version_id"],
            ["daily_candle_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["research_dataset_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "snapshot_id",
            "candle_version_id",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "company_id",
            "trading_day",
            name="uq_dataset_candle_company_day",
        ),
    )

    op.create_index(
        "ix_dataset_candle_members_snapshot_ticker_day",
        "research_dataset_candle_members",
        ["snapshot_id", "ticker_at_snapshot", "trading_day"],
    )

    op.create_index(
        "ix_dataset_candle_members_version",
        "research_dataset_candle_members",
        ["candle_version_id"],
    )

    # ------------------------------------------------------------------
    # Database immutability guards
    #
    # IMPORTANT:
    # asyncpg does not allow multiple SQL commands in one prepared
    # statement. Every CREATE FUNCTION / CREATE TRIGGER must therefore be
    # executed independently.
    # ------------------------------------------------------------------

    op.execute(
        """
        CREATE FUNCTION alphapilot_reject_candle_version_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'DailyCandleVersion rows are immutable';
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_daily_candle_versions_immutable
        BEFORE UPDATE OR DELETE ON daily_candle_versions
        FOR EACH ROW
        EXECUTE FUNCTION alphapilot_reject_candle_version_mutation();
        """
    )

    op.execute(
        """
        CREATE FUNCTION alphapilot_protect_terminal_ingestion_batch()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('COMPLETED', 'FAILED') THEN
                RAISE EXCEPTION 'Terminal ingestion batches are immutable';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_ingestion_batches_terminal_immutable
        BEFORE UPDATE OR DELETE ON market_data_ingestion_batches
        FOR EACH ROW
        EXECUTE FUNCTION alphapilot_protect_terminal_ingestion_batch();
        """
    )

    op.execute(
        """
        CREATE FUNCTION alphapilot_protect_finalized_snapshot()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'FINALIZED' THEN
                RAISE EXCEPTION 'Finalized research snapshots are immutable';
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_research_snapshots_finalized_immutable
        BEFORE UPDATE OR DELETE ON research_dataset_snapshots
        FOR EACH ROW
        EXECUTE FUNCTION alphapilot_protect_finalized_snapshot();
        """
    )

    op.execute(
        """
        CREATE FUNCTION alphapilot_protect_snapshot_member()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF EXISTS (
                    SELECT 1
                    FROM research_dataset_snapshots
                    WHERE id = NEW.snapshot_id
                      AND status = 'FINALIZED'
                ) THEN
                    RAISE EXCEPTION
                        'Finalized research snapshot members are immutable';
                END IF;

                RETURN NEW;
            END IF;

            IF TG_OP = 'DELETE' THEN
                IF EXISTS (
                    SELECT 1
                    FROM research_dataset_snapshots
                    WHERE id = OLD.snapshot_id
                      AND status = 'FINALIZED'
                ) THEN
                    RAISE EXCEPTION
                        'Finalized research snapshot members are immutable';
                END IF;

                RETURN OLD;
            END IF;

            -- UPDATE must protect BOTH sides:
            --
            -- 1. modifying an existing member of a finalized snapshot;
            -- 2. moving a member into a finalized snapshot.
            IF EXISTS (
                SELECT 1
                FROM research_dataset_snapshots
                WHERE id IN (OLD.snapshot_id, NEW.snapshot_id)
                  AND status = 'FINALIZED'
            ) THEN
                RAISE EXCEPTION
                    'Finalized research snapshot members are immutable';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_dataset_universe_members_immutable
        BEFORE INSERT OR UPDATE OR DELETE
        ON research_dataset_universe_members
        FOR EACH ROW
        EXECUTE FUNCTION alphapilot_protect_snapshot_member();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_dataset_candle_members_immutable
        BEFORE INSERT OR UPDATE OR DELETE
        ON research_dataset_candle_members
        FOR EACH ROW
        EXECUTE FUNCTION alphapilot_protect_snapshot_member();
        """
    )


def downgrade() -> None:
    # Keep each DDL operation separate for asyncpg compatibility.
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_dataset_candle_members_immutable
        ON research_dataset_candle_members
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_dataset_universe_members_immutable
        ON research_dataset_universe_members
        """
    )

    op.execute(
        "DROP FUNCTION IF EXISTS alphapilot_protect_snapshot_member()"
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_research_snapshots_finalized_immutable
        ON research_dataset_snapshots
        """
    )

    op.execute(
        "DROP FUNCTION IF EXISTS alphapilot_protect_finalized_snapshot()"
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_ingestion_batches_terminal_immutable
        ON market_data_ingestion_batches
        """
    )

    op.execute(
        "DROP FUNCTION IF EXISTS alphapilot_protect_terminal_ingestion_batch()"
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_daily_candle_versions_immutable
        ON daily_candle_versions
        """
    )

    op.execute(
        "DROP FUNCTION IF EXISTS alphapilot_reject_candle_version_mutation()"
    )

    op.drop_table("research_dataset_candle_members")
    op.drop_table("research_dataset_universe_members")
    op.drop_table("research_dataset_snapshots")
    op.drop_table("daily_candle_versions")
    op.drop_table("market_data_ingestion_batches")